from tclCommands.TclCommand import TclCommandSignaled

import logging
import collections
from copy import deepcopy
from shapely.ops import unary_union
from shapely import Polygon, LineString, LinearRing, MultiPolygon, MultiLineString

import gettext
import appTranslation as fcTranslate
import builtins

log = logging.getLogger('base')

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class TclCommandGeoCutout(TclCommandSignaled):
    """
        Tcl shell command to create a board cutout geometry.
        Allow cutout for any shape.
        Cuts holding gaps from geometry.

        example:

        """

    # List of all command aliases, to be able use old
    # names for backward compatibility (add_poly, add_polygon)
    aliases = ['geoc']

    description = '%s %s' % ("--", "Creates board cutout from an object (Gerber or Geometry) of any shape.")

    # Dictionary of types from Tcl command, needs to be ordered
    arg_names = collections.OrderedDict([
        ('name', str),
    ])

    # Dictionary of types from Tcl command, needs to be ordered,
    # this  is  for options  like -optionname value
    option_types = collections.OrderedDict([
        ('dia', float),
        ('margin', float),
        ('gapsize', float),
        ('gaps', str),
        ('outname', str)
    ])

    # array of mandatory options for current Tcl command: required = {'name','outname'}
    required = ['name']

    # structured help for current command, args needs to be ordered
    help = {
        'main': 'Creates board cutout from an object (Gerber or Geometry) of any shape.',
        'args': collections.OrderedDict([
            ('name', 'Name of the object to be cutout. Required'),
            ('dia', 'Tool diameter.'),
            ('margin', 'Margin over bounds.'),
            ('gapsize', 'size of gap.'),
            ('gaps', "type of gaps. Can be: 'None' = no-gaps, 'TB' = top-bottom, 'LR' = left-right, '2TB' = 2top-2bottom, "
                     "'2LR' = 2left-2right, '4' = 4 cuts, '8' = 8 cuts"),
            ('outname', 'Name of the resulting Geometry object.'),
        ]),
        'examples': ["      #isolate margin for example from Fritzing arduino shield or any svg etc\n" +
                     "      isolate BCu_margin -dia 3 -overlap 1\n" +
                     "\n" +
                     "      #create exteriors from isolated object\n" +
                     "      exteriors BCu_margin_iso -outname BCu_margin_iso_exterior\n" +
                     "\n" +
                     "      #delete isolated object if you dond need id anymore\n" +
                     "      delete BCu_margin_iso\n" +
                     "\n" +
                     "      #finally cut holding gaps\n" +
                     "      geocutout BCu_margin_iso_exterior -dia 3 -gapsize 0.6 -gaps 4 -outname cutout_geo\n"]
    }

    flat_geometry = []

    def execute(self, args, unnamed_args):
        """

        :param args:
        :param unnamed_args:
        :return:
        """

        # def subtract_rectangle(obj_, x0, y0, x1, y1):
        #     pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        #     obj_.subtract_polygon(pts)

        def substract_rectangle_geo(geo, x0, y0, x1, y1):
            pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

            def flatten(geometry=None, reset=True, pathonly=False):
                """
                Creates a list of non-iterable linear geometry objects.
                Polygons are expanded into its exterior and interiors if specified.

                Results are placed in flat_geometry

                :param geometry: Shapely type or list or list of list of such.
                :param reset: Clears the contents of self.flat_geometry.
                :param pathonly: Expands polygons into linear elements.
                """

                if reset:
                    self.flat_geometry = []

                # If iterable, expand recursively.
                try:
                    w_geo = geometry.geoms if isinstance(geometry, (MultiPolygon, MultiLineString)) else geometry
                    for geo_el in w_geo:
                        if geo_el is not None:
                            flatten(geometry=geo_el, reset=False, pathonly=pathonly)
                except TypeError:
                    # Not iterable, do the actual indexing and add.
                    if pathonly and type(geometry) == Polygon:
                        self.flat_geometry.append(geometry.exterior)
                        flatten(geometry=geometry.interiors, reset=False, pathonly=True)
                    else:
                        self.flat_geometry.append(geometry)

                return self.flat_geometry

            flat_geometry = flatten(geo, pathonly=True)

            polygon = Polygon(pts)
            toolgeo = unary_union(polygon)
            diffs = []
            for target in flat_geometry:
                if type(target) == LineString or type(target) == LinearRing:
                    diffs.append(target.difference(toolgeo))
                else:
                    self.app.log.warning("TclCommandGeoCutout.execute(). Not implemented.")
            return unary_union(diffs)

        if 'name' in args:
            name = args['name']
        else:
            msg = "[WARNING] %s" % _("The name of the object for which cutout is done is missing. Add it and retry.")
            self.app.log.warning(msg)
            return "fail"

        if 'margin' in args:
            margin = float(args['margin'])
        else:
            margin = float(self.app.options["tools_cutout_margin"])

        if 'dia' in args:
            dia = float(args['dia'])
        else:
            dia = float(self.app.options["tools_cutout_tooldia"])

        if 'gaps' in args:
            gaps = args['gaps']
        else:
            gaps = str(self.app.options["tools_cutout_gaps_ff"])

        if 'gapsize' in args:
            gapsize = float(args['gapsize'])
        else:
            gapsize = float(self.app.options["tools_cutout_gapsize"])

        if 'outname' in args:
            outname = args['outname']
        else:
            outname = str(name) + "_cutout"

        # Get source object.
        try:
            cutout_obj = self.app.collection.get_by_name(str(name))
        except Exception as e:
            self.app.log.error("TclCommandGeoCutout.execute() --> %s" % str(e))
            self.app.log.error("Could not retrieve object: %s" % name)
            return "fail"

        if 0 in {dia}:
            self.app.log.warning(
                "[WARNING] %s" % _("Tool Diameter is zero value. Change it to a positive real number."))
            return "fail"

        if str(gaps).lower() not in ['none', 'lr', 'tb', '2lr', '2tb', '4', '8']:
            self.app.log.warning('[WARNING] %s' %
                                 _("Gaps value can be only one of: 'none', 'lr', 'tb', '2lr', '2tb', 4 or 8.\n"
                                   "Fill in a correct value and retry."))
            return "fail"

        # Get min and max data for each object as we just cut rectangles across X or Y
        xmin, ymin, xmax, ymax = cutout_obj.bounds()
        cutout_obj.obj_options['xmin'] = xmin
        cutout_obj.obj_options['ymin'] = ymin
        cutout_obj.obj_options['xmax'] = xmax
        cutout_obj.obj_options['ymax'] = ymax

        px = 0.5 * (xmin + xmax) + margin
        py = 0.5 * (ymin + ymax) + margin
        lenghtx = (xmax - xmin) + (margin * 2)
        lenghty = (ymax - ymin) + (margin * 2)

        gapsize = gapsize / 2 + (dia / 2)

        try:
            gaps_u = int(gaps)
        except ValueError:
            gaps_u = gaps

        if cutout_obj.kind == 'geometry':
            geo_to_cutout = deepcopy(cutout_obj.solid_geometry)
        elif cutout_obj.kind == 'gerber':
            try:
                geo_to_cutout = cutout_obj.isolation_geometry((dia / 2), iso_type=0, corner=2)
            except Exception as exc:
                self.app.log.error("TclCommandGeoCutout.execute() --> %s" % str(exc))
                return 'fail'
        else:
            self.app.log.error("[ERROR] %s" % _("Cancelled. Object type is not supported."))
            return "fail"

        def geo_init(geo_obj, app_obj):
            geo_obj.multigeo = True
            geo = geo_to_cutout

            if gaps_u == 8 or gaps_u == '2LR':
                geo = substract_rectangle_geo(geo,
                                              xmin - gapsize,               # botleft_x
                                              py - gapsize + lenghty / 4,   # botleft_y
                                              xmax + gapsize,               # topright_x
                                              py + gapsize + lenghty / 4)   # topright_y
                geo = substract_rectangle_geo(geo,
                                              xmin - gapsize,
                                              py - gapsize - lenghty / 4,
                                              xmax + gapsize,
                                              py + gapsize - lenghty / 4)

            if gaps_u == 8 or gaps_u == '2TB':
                geo = substract_rectangle_geo(geo,
                                              px - gapsize + lenghtx / 4,
                                              ymin - gapsize,
                                              px + gapsize + lenghtx / 4,
                                              ymax + gapsize)
                geo = substract_rectangle_geo(geo,
                                              px - gapsize - lenghtx / 4,
                                              ymin - gapsize,
                                              px + gapsize - lenghtx / 4,
                                              ymax + gapsize)

            if gaps_u == 4 or gaps_u == 'LR':
                geo = substract_rectangle_geo(geo,
                                              xmin - gapsize,
                                              py - gapsize,
                                              xmax + gapsize,
                                              py + gapsize)

            if gaps_u == 4 or gaps_u == 'TB':
                geo = substract_rectangle_geo(geo,
                                              px - gapsize,
                                              ymin - gapsize,
                                              px + gapsize,
                                              ymax + gapsize)

            geo_obj.solid_geometry = deepcopy(geo)
            geo_obj.obj_options['xmin'] = cutout_obj.obj_options['xmin']
            geo_obj.obj_options['ymin'] = cutout_obj.obj_options['ymin']
            geo_obj.obj_options['xmax'] = cutout_obj.obj_options['xmax']
            geo_obj.obj_options['ymax'] = cutout_obj.obj_options['ymax']

            if not geo_obj.solid_geometry:
                app_obj.log("TclCommandGeoCutout.execute(). No geometry after geo-cutout.")
                return "fail"

            default_tool_data = self.app.options.copy()

            geo_obj.tools = {
                1: {
                    'tooldia': dia,
                    'data': default_tool_data,
                    'solid_geometry': deepcopy(geo_obj.solid_geometry)
                }
            }
            geo_obj.tools[1]['data']['tools_cutout_tooldia'] = dia
            geo_obj.tools[1]['data']['tools_cutout_gaps_ff'] = gaps
            geo_obj.tools[1]['data']['tools_cutout_margin'] = margin
            geo_obj.tools[1]['data']['tools_cutout_gapsize'] = gapsize

            app_obj.disable_plots(objects=[cutout_obj])

        ret = self.app.app_obj.new_object('geometry', outname, geo_init, plot=False)
        if ret == 'fail':
            msg = "Could not create a geo-cutout Geometry object from a %s object." % cutout_obj.kind.capialize()
            self.app.log.error(msg)
            return "fail"
        else:
            self.app.log.info("[success] %s" % _("Any-form Cutout operation finished."))
