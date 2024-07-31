from tclCommands.TclCommand import TclCommand

import collections


class TclCommandExportSVG(TclCommand):
    """
    Tcl shell command to export a Geometry Object as an SVG File.

    example:
        export_svg my_geometry filename
    """

    # List of all command aliases, to be able to use old names for backward compatibility (add_poly, add_polygon)
    aliases = ['export_svg']

    description = '%s %s' % ("--", "Export a Geometry object as a SVG File.")

    # Dictionary of types from Tcl command, needs to be ordered
    arg_names = collections.OrderedDict([
        ('name', str),
        ('filename', str),
    ])

    # Dictionary of types from Tcl command, needs to be ordered , this  is  for options  like -optionname value
    option_types = collections.OrderedDict([
        ('scale_stroke_factor', float)
    ])

    # array of mandatory options for current Tcl command: required = {'name','outname'}
    required = ['name']

    # structured help for current command, args needs to be ordered
    help = {
        'main': "Export a Geometry object as a SVG File.",
        'args': collections.OrderedDict([
            ('name', 'Name of the object export. Required.'),
            ('filename', 'Absolute path to file to export.\n'
                         'WARNING: no spaces are allowed. If unsure enclose the entire path with quotes.'),
            ('scale_stroke_factor', 'Multiplication factor used for scaling line widths during export.')
        ]),
        'examples': ['export_svg my_geometry my_file.svg']
    }

    def execute(self, args, unnamed_args):
        """

        :param args:
        :param unnamed_args:
        :return:
        """

        if 'name' not in args:
            return "Failed. The Geometry object name to be exported was not provided."

        source_obj_name = args['name']

        if 'filename' not in args:
            filename = self.app.options["global_last_save_folder"] + '/' + args['name']
        else:
            filename = args['filename']

        if 'scale_stroke_factor' in args and args['scale_stroke_factor'] != 0.0:
            str_factor = args['scale_stroke_factor']
        else:
            str_factor = 0.0
        self.app.f_handlers.export_svg(obj_name=source_obj_name, filename=filename, scale_stroke_factor=str_factor)
