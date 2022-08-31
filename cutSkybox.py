from __future__ import print_function

import os.path
import pathlib

from PIL import Image


def main(cubemap_name):
    infile = cubemap_name
    file_extension = ".png"

    name_map = [
        ["", "", "posy", ""],
        ["negz", "negx", "posz", "posx"],
        ["", "", "negy", ""]
    ]

    try:
        # Create dir for cut cubemap
        parent_dir = str(pathlib.Path(__file__).parent.resolve()) + "/"
        pre, ext = os.path.splitext(parent_dir + cubemap_name)
        directory = pre.split(sep='/')[-1] + "-cropped/"
        path = os.path.join(parent_dir, directory)
        os.mkdir(path)

        # Cutting the cubemap
        im = Image.open(infile)
        print(infile, im.format, "%dx%d" % im.size, im.mode)

        width, height = im.size

        cube_size = width / 4

        filelist = []
        for row in range(3):
            for col in range(4):
                if name_map[row][col] != "":
                    sx = cube_size * col
                    sy = cube_size * row
                    fn = name_map[row][col] + file_extension
                    filelist.append(fn)
                    print("%s --> %s" % (str((sx, sy, sx + cube_size, sy + cube_size)), fn))
                    im.crop((sx, sy, sx + cube_size, sy + cube_size)).save(path + fn)

        return str(path + "/negz.png")  # if camera is parallel to the exit (directly facing)
        # return str(path + "/posx.png")  # if camera is perpendicular to the exit (90 deg to the right side)
    except IOError:
        pass
