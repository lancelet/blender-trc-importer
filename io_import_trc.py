# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

bl_info = {
    'name': 'Import TRC motion capture files (*.trc)',
    'author': 'Jonathan Merritt',
    'version': (0, 1, 0),
    'blender': (2, 6, 3),
    'location': 'File > Import > Motion capture (.trc)',
    'description': 'Import TRC motion capture files (.trc)',
    'warning': 'In development.',
    'wiki_url': 'https://github.com/lancelet/blender-trc-importer/wiki',
    'tracker_url': 'https://github.com/lancelet/blender-trc-importer/issues',
    'support': 'TESTING',
    'category': 'Import-Export',
}

"""
This script imports TRC motion capture files to Blender.

Description...

Usage:
Execute this script from the "File->Import menu and choose a TRC file to open.

Notes:
...
"""

__version__ = '.'.join([str(s) for s in bl_info['version']])

import csv

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from bpy.types import Operator
import mathutils
from mathutils import Vector

SCALE = 0.001 # TODO: make scaling a script option

class TRCData:
    markers = {}         # map of marker names to sequence of mathutils.Vector
    data_rate = 0.0      # data rate (Hz)
    camera_rate = 0.0    # camera rate (Hz)
    num_frames = 0       # number of frames
    num_markers = 0      # number of markers
    units = "mm"         # measurement units
    orig_data_rate = 0.0 # original data rate (Hz)
    orig_data_start = 0  # original data start frame
    orig_num_frames = 0  # original number of frames 


def read_trc(context, filepath):
    """Reads a TRC file, returning a TRCData class."""
    
    # open the file and read it as CSV
    file = open(filepath, 'r', encoding='utf-8')
    reader = csv.reader(file, 'excel-tab')
    data = TRCData()
    
    # drop the first two lines of the file.  TODO: validate header contents
    reader.__next__(); reader.__next__()
    
    # grab the meta data from the next line
    md = reader.__next__()
    data.data_rate = float(md[0])
    data.camera_rate = float(md[1])
    data.num_frames = int(md[2])
    data.num_markers = int(md[3])
    data.units = md[4]
    data.orig_data_rate = float(md[5])
    data.orig_data_start = int(md[6])
    data.orig_num_frames = int(md[7])
    
    # grab marker-names from the next line (every third entry)
    marker_nl = (reader.__next__())[2:-1]
    marker_names = [marker_nl[i] for i in range(len(marker_nl)) if i % 3 == 0]
    for mn in marker_names:
        data.markers[mn] = []
    # drop xyz label line and blank line following
    reader.__next__(); reader.__next__()
    
    # read in remaining lines until the end of the file (coordinate data)
    for line in reader:
        rt = line[2:-1]
        assert(len(rt) % 3 == 0)
        index = 0
        for marker_name in marker_names:
            ofs = index * 3
            co = rt[ofs:ofs + 3]
            index = index + 1
            try:
                x = float(co[0])
                y = float(co[1])
                z = float(co[2])
                v = Vector((x, y, z))
                data.markers[marker_name].append(v)
            except ValueError:
                data.markers[marker_name].append(None)    
    
    # close up the file and return
    file.close()
    return data


def import_trc(context, filepath):
    """Reads a TRC file and imports it into Blender."""
    data = read_trc(context, filepath)
    for marker_name in data.markers.keys():
        # create the object
        bpy.ops.object.add()
        obj = bpy.context.active_object
        # name it and set properties
        obj.name = marker_name
        obj.empty_draw_type = "SPHERE"  # TODO: Option?
        obj.empty_draw_size = SCALE * 20
        # create animation action and fcurves
        obj.animation_data_create()
        obj.animation_data.action = bpy.data.actions.new(name="MocapAction")
        act = obj.animation_data.action
        fcu_x = act.fcurves.new(data_path="location", index = 0)
        fcu_y = act.fcurves.new(data_path="location", index = 1)
        fcu_z = act.fcurves.new(data_path="location", index = 2)
        fcu_h = act.fcurves.new(data_path="hide")
        fcu_r = act.fcurves.new(data_path="hide_render")
        # allocate keyframes
        m = data.markers[marker_name]
        n_frames = len(m)
        n_loc_frames = len([x for x in m if x is not None])
        fcu_x.keyframe_points.add(n_loc_frames)
        fcu_y.keyframe_points.add(n_loc_frames)
        fcu_z.keyframe_points.add(n_loc_frames)
        fcu_h.keyframe_points.add(n_frames)
        fcu_r.keyframe_points.add(n_frames)
        # set keyframes
        index = 0
        keyframe_index = 0
        index_to_time = bpy.context.scene.render.fps / data.camera_rate
        for v in m:
            time = index * index_to_time
            if v is not None:
                fcu_x.keyframe_points[keyframe_index].co = time, v[0] * SCALE
                fcu_y.keyframe_points[keyframe_index].co = time, v[1] * SCALE
                fcu_z.keyframe_points[keyframe_index].co = time, v[2] * SCALE
                fcu_h.keyframe_points[index].co = time, 0
                fcu_r.keyframe_points[index].co = time, 0
                keyframe_index = keyframe_index + 1
            else:
                fcu_h.keyframe_points[index].co = time, 1
                fcu_r.keyframe_points[index].co = time, 1
            index = index + 1


class IMPORT_OT_mocap_trc(Operator, ImportHelper):
    """Import from TRC file format (.trc)"""
    bl_idname = "import_scene.mocap_trc"
    bl_description = "Import from TRC file format (.trc)"
    bl_label = "Import TRC" + " v." + __version__

    filename_ext = ".trc"
    filter_glob = StringProperty(default="*.trc", options={"HIDDEN"})

    def execute(self, context):
        import_trc(context, self.filepath)
        return {"FINISHED"}


def menu_func(self, context):
    self.layout.operator(IMPORT_OT_mocap_trc.bl_idname, 
        text="Motion Capture (.trc)")


def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menu_func)


def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menu_func)


if __name__ == '__main__':
    register()
    
    # test call
    bpy.ops.import_scene.mocap_trc('INVOKE_DEFAULT')