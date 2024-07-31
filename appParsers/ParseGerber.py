
from PyQt6 import QtWidgets
from camlib import Geometry, arc, arc_angle, ApertureMacro, grace, flatten_shapely_geometry

from appParsers.ParseDXF import getdxfgeo
from appParsers.ParseSVG import svgparselength, getsvggeo, svgparse_viewbox

import numpy as np
import traceback
from copy import deepcopy

from shapely.ops import unary_union, linemerge
import shapely.affinity as affinity
from shapely import box as shply_box
from shapely import LinearRing, MultiLineString, LineString, Polygon, MultiPolygon, Point, prepare, is_prepared

from lxml import etree as ET
import ezdxf
import logging
import re
import sys

import gettext
import builtins

if '_' not in builtins.__dict__:
    _ = gettext.gettext

log = logging.getLogger('base')


class Gerber(Geometry):
    """
    Here it is done all the Gerber parsing.

    **ATTRIBUTES**

    * ``tools`` (dict): The keys are names/identifiers of each aperture.
      The values are dictionaries key/value pairs which describe the aperture. The
      type key is always present and the rest depend on the key:

    +-----------+-----------------------------------+
    | Key       | Value                             |
    +===========+===================================+
    | type      | (str) "C", "R", "O", "P", or "AP" |
    +-----------+-----------------------------------+
    | others    | Depend on ``type``                |
    +-----------+-----------------------------------+
    | geometry      | (list)                  |
    +-----------+-----------------------------------+
    * ``aperture_macros`` (dictionary): Are predefined geometrical structures
      that can be instantiated with different parameters in an aperture
      definition. See ``apertures`` above. The key is the name of the macro,
      and the macro itself, the value, is a ``Aperture_Macro`` object.

    * ``flash_geometry`` (list): List of (Shapely) geometric object resulting
      from ``flashes``. These are generated from ``flashes`` in ``do_flashes()``.

    * ``buffered_paths`` (list): List of (Shapely) polygons resulting from
      *buffering* (or thickening) the ``paths`` with the aperture. These are
      generated from ``paths`` in ``buffer_paths()``.

    **USAGE**::

        g = Gerber()
        g.parse_file(filename)
        g.create_geometry()
        do_something(s.solid_geometry)

    """

    # defaults = {
    #     "steps_per_circle": 128,
    #     "use_buffer_for_union": True
    # }

    app = None

    def __init__(self, steps_per_circle=None):
        """
        Use ``gerber.parse_files()`` or ``gerber.parse_lines()`` to populate the object from Gerber source.

        :return: Gerber object
        :rtype: Gerber
        """

        # How to approximate a circle with lines.
        if steps_per_circle is None:
            self.steps_per_circle = int(self.app.options["gerber_circle_steps"])
        else:
            self.steps_per_circle = steps_per_circle
        self.decimals = self.app.decimals

        # Initialize parent
        Geometry.__init__(self, geo_steps_per_circle=self.steps_per_circle)

        # Number format
        self.int_digits = 3
        """Number of integer digits in Gerber numbers. Used during parsing."""

        self.frac_digits = 4
        """Number of fraction digits in Gerber numbers. Used during parsing."""

        self.gerber_zeros = self.app.options['gerber_def_zeros']
        """Zeros in Gerber numbers. If 'L' then remove leading zeros, if 'T' remove trailing zeros. Used during parsing.
        """

        # ## Gerber elements # ##
        '''
        tools = {
            aperture_id:{
                'type':string, 
                'size':float, 
                'width':float,
                'height':float,
                'geometry': [],
            }
        }
        tools[aperture_id]['geometry'] list elements are dicts
        dict = {
            'solid': [],
            'follow': [],
            'clear': []
        }
        '''

        # store the file units here:
        self.units = self.app.options['gerber_def_units']

        # aperture storage
        self.tools = {}

        # Aperture Macros
        self.aperture_macros = {}

        # will store the Gerber geometry's as solids
        self.solid_geometry = Polygon()

        # will store the Gerber geometry's as paths
        self.follow_geometry = []

        # made True when the LPC command is encountered in Gerber parsing
        # it allows adding data into the clear_geometry key of the self.tools[aperture] dict
        self.is_lpc = False

        self.source_file = ''

        # #############################################################################################################
        # ################################# Parser patterns ###########################################################
        # #############################################################################################################

        # Detect Gerber x2 format
        self.gx2_re = re.compile(r'%TF\.FileFunction.*')

        # FS - Format Specification
        # The format of X and Y must be the same!
        # L-omit leading zeros, T-omit trailing zeros, D-no zero supression
        # A-absolute notation, I-incremental notation
        self.fmt_re = re.compile(r'%?FS([LTD])?([AI])X(\d)(\d)Y\d\d\*%?$')
        self.fmt_re_alt = re.compile(r'%FS([LTD])?([AI])X(\d)(\d)Y\d\d\*MO(IN|MM)\*%$')
        self.fmt_re_orcad = re.compile(r'(G\d+)*\**%FS([LTD])?([AI]).*X(\d)(\d)Y\d\d\*%$')

        # Mode (IN/MM)
        self.mode_re = re.compile(r'^%?MO(IN|MM)\*%?$')

        # Comment G04|G4
        self.comm_re = re.compile(r'^G0?4(.*)$')

        # AD - Aperture definition
        # Aperture Macro names: Name = [a-zA-Z_.$]{[a-zA-Z_.0-9]+}
        # NOTE: Adding "-" to support output from Upverter.
        self.ad_re = re.compile(r'^%ADD(\d\d+)([a-zA-Z_$\.][a-zA-Z0-9_$\.\-]*)(?:,(.*))?\*%$')

        # AM - Aperture Macro
        # Beginning of macro (Ends with *%):
        # self.am_re = re.compile(r'^%AM([a-zA-Z0-9]*)\*')

        # Tool change
        # May begin with G54 but that is deprecated
        self.tool_re = re.compile(r'^(?:G54)?D(\d\d+)\*$')

        # G01... - Linear interpolation plus flashes with coordinates
        # Operation code (D0x) missing is deprecated... oh well I will support it.
        self.lin_re = re.compile(r'^(?:G0?(1))?(?=.*X([+-]?\d+))?(?=.*Y([+-]?\d+))?[XY][^DIJ]*(?:D0?([123]))?\*$')

        # Operation code alone, usually just D03 (Flash)
        # May begin with G55 but that is deprecated
        self.opcode_re = re.compile(r'^(?:G55)?D0?([123])\*$')

        # G02/3... - Circular interpolation with coordinates
        # 2-clockwise, 3-counterclockwise
        # Operation code (D0x) missing is deprecated... oh well I will support it.
        # Optional start with G02 or G03, optional end with D01 or D02 with
        # optional coordinates but at least one in any order.
        self.circ_re = re.compile(
            r'^(?:G0?([23]))?(?=.*X([+-]?\d+))?(?=.*Y([+-]?\d+))' +
            '?(?=.*I([+-]?\d+))?(?=.*J([+-]?\d+))?[XYIJ][^D]*(?:D0([12]))?\*$'
        )

        # G01/2/3 Occurring without coordinates
        self.interp_re = re.compile(r'^(?:G0?([123]))\*')

        # Single G74 or multi G75 quadrant for circular interpolation
        self.quad_re = re.compile(r'^G7([45]).*\*$')

        # Region mode on
        # In region mode, D01 starts a region
        # and D02 ends it. A new region can be started again
        # with D01. All contours must be closed before
        # D02 or G37.
        self.regionon_re = re.compile(r'^G36\*$')

        # Region mode off
        # Will end a region and come off region mode.
        # All contours must be closed before D02 or G37.
        self.regionoff_re = re.compile(r'^G37\*$')

        # End of file
        self.eof_re = re.compile(r'^M02\*')

        # IP - Image polarity
        self.pol_re = re.compile(r'^%?IP(POS|NEG)\*%?$')

        # LP - Level polarity
        self.lpol_re = re.compile(r'^%LP([DC])\*%$')

        # Units (OBSOLETE)
        self.units_re = re.compile(r'^G7([01])\*$')

        # Absolute/Relative G90/1 (OBSOLETE)
        self.absrel_re = re.compile(r'^G9([01])\*$')

        # Aperture macros
        self.am1_re = re.compile(r'^%AM([^\*]+)\*([^%]+)?(%)?$')
        self.am2_re = re.compile(r'(.*)%$')

        # flag to store if a conversion was done. It is needed because multiple units declarations can be found
        # in a Gerber file (normal or obsolete ones)
        self.conversion_done = False

        # Flag to detect if an aperture is used without definition
        self.defective_aperture_detected = False

        self.use_buffer_for_union = self.app.options["gerber_use_buffer_for_union"]

        # Attributes to be included in serialization
        # Always append to it because it carries contents
        # from Geometry.
        self.ser_attrs += ['tools', 'int_digits', 'frac_digits', 'aperture_macros', 'solid_geometry', 'source_file']

    def aperture_parse(self, apertureId, apertureType, apParameters):
        """
        Parse gerber aperture definition into dictionary of apertures.
        The following kinds and their attributes are supported:

        * *Circular (C)*: size (float)
        * *Rectangle (R)*: width (float), height (float)
        * *Obround (O)*: width (float), height (float).
        * *Polygon (P)*: diameter(float), vertices(int), [rotation(float)]
        * *Aperture Macro (AM)*: macro (ApertureMacro), modifiers (list)

        :param apertureId: Id of the aperture being defined.
        :param apertureType: Type of the aperture.
        :param apParameters: Parameters of the aperture.
        :type apertureId: str
        :type apertureType: str
        :type apParameters: str
        :return: Identifier of the aperture.
        :rtype: str
        """
        if self.app.abort_flag:
            # graceful abort requested by the user
            raise grace

        # Found some Gerber with a leading zero in the aperture id and the
        # referenced it without the zero, so this is a hack to handle that.
        apid = int(apertureId)

        try:  # Could be empty for aperture macros
            paramList = apParameters.split('X')
        except Exception:
            paramList = None

        if apertureType == "C":  # Circle, example: %ADD11C,0.1*%
            self.tools[apid] = {
                "type": "C",
                "size": float(paramList[0])
            }
            return apid

        if apertureType == "R":  # Rectangle, example: %ADD15R,0.05X0.12*%
            self.tools[apid] = {
                "type": "R",
                "width": float(paramList[0]),
                "height": float(paramList[1]),
                "size": np.sqrt(float(paramList[0]) ** 2 + float(paramList[1]) ** 2)}  # Hack
            return apid

        if apertureType == "O":  # Obround
            self.tools[apid] = {
                "type": "O",
                "width": float(paramList[0]),
                "height": float(paramList[1]),
                "size": np.sqrt(float(paramList[0]) ** 2 + float(paramList[1]) ** 2)}  # Hack
            return apid

        if apertureType == "P":  # Polygon (regular)
            self.tools[apid] = {
                "type": "P",
                "diam": float(paramList[0]),
                "nVertices": int(paramList[1]),
                "size": float(paramList[0])}  # Hack
            if len(paramList) >= 3:
                self.tools[apid]["rotation"] = float(paramList[2])
            return apid

        if apertureType in self.aperture_macros:
            self.tools[apid] = {
                "type": "AM",
                # "size": 0.0,
                "macro": self.aperture_macros[apertureType],
                "modifiers": paramList
            }
            return apid

        self.app.log.warning("Aperture not implemented: %s" % str(apertureType))
        return None

    def parse_file(self, filename, follow=False):
        """
        Calls Gerber.parse_lines() with generator of lines
        read from the given file. Will split the lines if multiple
        statements are found in a single original line.

        The following line is split into two::

            G54D11*G36*

        First is ``G54D11*`` and seconds is ``G36*``.

        :param filename:        Gerber file to parse.
        :type filename:         str
        :param follow:          If true, will not create polygons, just lines
                                following the gerber path.
        :type follow:           bool
        :return:                None
        """

        with open(filename, 'r') as gfile:

            read_gfile = gfile.read()

            # clean KiCAD files of garbage
            if '%TF.' in read_gfile or '%TO.' in read_gfile or '%TD' in read_gfile or '%TA' in read_gfile:
                new_gfile = ""
                for line in read_gfile.splitlines():
                    if '%TF.' in line or '%TO.' in line or '%TD' in line or '%TA' in line:
                        continue
                    new_gfile += '%s\n' % line
                split_lines = new_gfile.splitlines()
            else:
                split_lines = read_gfile.splitlines()

            def line_generator():
                for line in split_lines:
                    line = line.strip(' \r\n')
                    while len(line) > 0:

                        # If ends with '%' leave as is.
                        if line[-1] == '%':
                            yield line
                            break

                        # Split after '*' if any.
                        starpos = line.find('*')
                        if starpos > -1:
                            cleanline = line[:starpos + 1]
                            yield cleanline
                            line = line[starpos + 1:]

                        # Otherwise leave as is.
                        else:
                            # yield clean line
                            yield line
                            break

            processed_lines = list(line_generator())
            ret_val = self.parse_lines(processed_lines)

            if ret_val == 'fail':
                return 'fail'
            elif ret_val == "defective":
                return "defective"
            elif ret_val == 'drill':
                return 'drill_gx2'
            else:
                return

    # @profile
    def parse_lines(self, glines):
        """
        Main Gerber parser. Reads Gerber and populates ``self.paths``, ``self.tools``,
        ``self.flashes``, ``self.regions`` and ``self.units``.

        :param glines: Gerber code as list of strings, each element being
            one line of the source file.
        :type glines: list
        :return: only errors/warnings
        :rtype: str
        """

        is_excellon_gx2 = False

        # Coordinates of the current path, each is [x, y]
        path = []

        # this is for temporary storage of solid geometry until it is added to poly_buffer
        geo_s = None

        # this is for temporary storage of follow geometry until it is added to follow_buffer
        geo_f = None

        # Polygons are stored here until there is a change in polarity.
        # Only then they are combined via unary_union and added or
        # subtracted from solid_geometry. This is ~100 times faster than
        # applying a union for every new polygon.
        poly_buffer = []

        # store here the follow geometry
        follow_buffer = []

        last_path_aperture = None
        current_aperture = None

        # 1,2 or 3 from "G01", "G02" or "G03"
        current_interpolation_mode = None

        # 1 or 2 from "D01" or "D02"
        # Note this is to support deprecated Gerber not putting
        # an operation code at the end of every coordinate line.
        current_operation_code = None

        # Current coordinates
        current_x = 0
        current_y = 0

        current_d = None

        # Absolute or Relative/Incremental coordinates
        # Not implemented
        # absolute = True

        # How to interpret circular interpolation: SINGLE or MULTI
        quadrant_mode = None

        # Indicates we are parsing an aperture macro
        current_macro = None

        # Indicates the current polarity: D-Dark, C-Clear
        current_polarity = 'D'

        # If a region is being defined
        making_region = False

        # ### Parsing starts here ## ##
        line_num = 0
        gline = ""

        s_tol = float(self.app.options["gerber_simp_tolerance"])

        self.app.inform.emit('%s %d %s.' % (_("Gerber processing. Parsing"), len(glines), _("Lines").lower()))
        try:
            for gline in glines:
                if self.app.abort_flag:
                    # graceful abort requested by the user
                    raise grace

                line_num += 1
                self.source_file += gline + '\n'

                # Cleanup #
                gline = gline.strip(' \r\n')
                # self.app.log.debug("Line=%3s %s" % (line_num, gline))

                # ###############################################################
                # ################   Ignored lines   ############################
                # ################     Comments      ############################
                # ###############################################################
                match = self.comm_re.search(gline)
                if match:
                    continue

                # ######################################################################################################
                # ######## Detect GERBER X2 format #####################################################################
                # ######################################################################################################
                match = self.gx2_re.search(gline)
                if match:
                    self.app.log.warning('Gerber X2 format detected !!!')
                    self.app.inform.emit(
                        '[WARNING] %s' % _('Gerber X2 format detected. Parsing may not be done correctly.'))
                    if 'Drill' in gline:
                        self.app.log.warning('Drill file in Gerber X2 format detected !!!')
                        self.app.inform.emit(
                            '[WARNING] %s' % _('Drill file Gerber X2 format detected. '
                                               'Parsing may not be done correctly.'))
                        is_excellon_gx2 = True
                    continue

                # ###############################################################
                # ################  Polarity change #############################
                # ########   Example: %LPD*% or %LPC*%        ###################
                # ########   If polarity changes, creates geometry from current #
                # ########    buffer, then adds or subtracts accordingly.       #
                # ###############################################################
                match = self.lpol_re.search(gline)
                if match:
                    new_polarity = match.group(1)
                    # self.app.log.info("Polarity CHANGE, LPC = %s, poly_buff = %s" % (self.is_lpc, poly_buffer))
                    self.is_lpc = True if new_polarity == 'C' else False
                    try:
                        path_length = len(path)
                    except TypeError:
                        path_length = 1

                    if path_length > 1 and current_polarity != new_polarity:

                        # finish the current path and add it to the storage
                        # --- Buffered ----
                        width = self.tools[last_path_aperture]["size"]

                        geo_dict = {}
                        geo_f = LineString(path)
                        prepare(geo_f)
                        if not geo_f.is_empty:
                            follow_buffer.append(geo_f)
                            geo_dict['follow'] = geo_f

                        geo_s = LineString(path).buffer(width / 1.999, int(self.steps_per_circle))
                        if self.app.options['gerber_simplification']:
                            geo_s = geo_s.simplify(s_tol)
                        if not geo_s.is_empty and geo_s.is_valid:
                            prepare(geo_s)
                            poly_buffer.append(geo_s)

                            if self.is_lpc is True:
                                geo_dict['clear'] = geo_s
                            else:
                                geo_dict['solid'] = geo_s

                        if last_path_aperture not in self.tools:
                            self.tools[last_path_aperture] = {}
                        if 'geometry' not in self.tools[last_path_aperture]:
                            self.tools[last_path_aperture]['geometry'] = []
                        self.tools[last_path_aperture]['geometry'].append(geo_dict)

                        path = [path[-1]]

                    # --- Apply buffer ---
                    # If added for testing of bug #83
                    # TODO: Remove when bug fixed
                    try:
                        buff_length = len(poly_buffer)
                    except TypeError:
                        buff_length = 1

                    if buff_length > 0:
                        if current_polarity == 'D':
                            self.solid_geometry = self.solid_geometry.union(unary_union(poly_buffer))

                        else:
                            self.solid_geometry = self.solid_geometry.difference(unary_union(poly_buffer))

                        # follow_buffer = []
                        poly_buffer = []

                    current_polarity = new_polarity
                    continue

                # ################################################################
                # #####################  Number format ###########################
                # #####################  Example: %FSLAX24Y24*%  #################
                # ################################################################

                match = self.fmt_re.search(gline)
                if match:
                    absolute = {'A': 'Absolute', 'I': 'Relative'}[match.group(2)]
                    if match.group(1) is not None:
                        self.gerber_zeros = match.group(1)
                    self.int_digits = int(match.group(3))
                    self.frac_digits = int(match.group(4))
                    self.app.log.debug("Gerber format found. (%s) " % str(gline))

                    self.app.log.debug(
                        "Gerber format found. Gerber zeros = %s (L-omit leading zeros, T-omit trailing zeros, "
                        "D-no zero supression)" % self.gerber_zeros)
                    self.app.log.debug("Gerber format found. Coordinates type = %s (Absolute or Relative)" % absolute)
                    continue

                # ################################################################
                # ######################## Mode (IN/MM)    #######################
                # #####################    Example: %MOIN*%  #####################
                # ################################################################
                match = self.mode_re.search(gline)
                if match:
                    self.units = match.group(1)
                    self.app.log.debug("Gerber units found = %s" % self.units)
                    # Changed for issue #80
                    # self.convert_units(match.group(1))
                    s_tol = float(self.app.options["gerber_simp_tolerance"]) / 25.4 if self.units == 'IN' else s_tol

                    self.conversion_done = True
                    continue

                # ################################################################
                # Combined Number format and Mode --- Allegro does this ##########
                # ################################################################
                match = self.fmt_re_alt.search(gline)
                if match:
                    absolute = {'A': 'Absolute', 'I': 'Relative'}[match.group(2)]
                    if match.group(1) is not None:
                        self.gerber_zeros = match.group(1)
                    self.int_digits = int(match.group(3))
                    self.frac_digits = int(match.group(4))
                    self.app.log.debug("Gerber format found. (%s) " % str(gline))
                    self.app.log.debug(
                        "Gerber format found. Gerber zeros = %s (L-omit leading zeros, T-omit trailing zeros, "
                        "D-no zero suppression)" % self.gerber_zeros)
                    self.app.log.debug("Gerber format found. Coordinates type = %s (Absolute or Relative)" % absolute)

                    self.units = match.group(5)
                    s_tol = float(self.app.options["gerber_simp_tolerance"]) / 25.4 if self.units == 'IN' else s_tol

                    self.app.log.debug("Gerber units found = %s" % self.units)
                    # Changed for issue #80
                    # self.convert_units(match.group(5))
                    self.conversion_done = True
                    continue

                # ################################################################
                # ####     Search for OrCAD way for having Number format  ########
                # ################################################################
                match = self.fmt_re_orcad.search(gline)
                if match:
                    if match.group(1) is not None:
                        if match.group(1) == 'G74':
                            quadrant_mode = 'SINGLE'
                        elif match.group(1) == 'G75':
                            quadrant_mode = 'MULTI'
                        absolute = {'A': 'Absolute', 'I': 'Relative'}[match.group(3)]
                        if match.group(2) is not None:
                            self.gerber_zeros = match.group(2)

                        self.int_digits = int(match.group(4))
                        self.frac_digits = int(match.group(5))
                        self.app.log.debug("Gerber format found. (%s) " % str(gline))
                        self.app.log.debug(
                            "Gerber format found. Gerber zeros = %s (L-omit leading zeros, T-omit trailing zeros, "
                            "D-no zerosuppressionn)" % self.gerber_zeros)
                        self.app.log.debug(
                            "Gerber format found. Coordinates type = %s (Absolute or Relative)" % absolute)

                        self.units = match.group(1)
                        s_tol = float(
                            self.app.options["gerber_simp_tolerance"]) / 25.4 if self.units == 'IN' else s_tol

                        self.app.log.debug("Gerber units found = %s" % self.units)
                        # Changed for issue #80
                        # self.convert_units(match.group(5))
                        self.conversion_done = True
                        continue

                # ################################################################
                # ############     Units (G70/1) OBSOLETE   ######################
                # ################################################################
                match = self.units_re.search(gline)
                if match:
                    obs_gerber_units = {'0': 'IN', '1': 'MM'}[match.group(1)]
                    self.units = obs_gerber_units
                    s_tol = float(self.app.options["gerber_simp_tolerance"]) / 25.4 if self.units == 'IN' else s_tol

                    self.app.log.warning("Gerber obsolete units found = %s" % obs_gerber_units)
                    # Changed for issue #80
                    # self.convert_units({'0': 'IN', '1': 'MM'}[match.group(1)])
                    self.conversion_done = True
                    continue

                # ################################################################
                # #####   Absolute/relative coordinates G90/1 OBSOLETE ###########
                # ################################################################
                match = self.absrel_re.search(gline)
                if match:
                    absolute = {'0': "Absolute", '1': "Relative"}[match.group(1)]
                    self.app.log.warning(
                        "Gerber obsolete coordinates type found = %s (Absolute or Relative) " % absolute)
                    continue

                # ################################################################
                # ######################## Aperture Macros #######################
                # Having this at the beginning will slow things down
                # but macros can have complicated statements than could
                # be caught by other patterns.
                # ################################################################
                # ################################################################
                if current_macro is None:  # No macro started yet
                    match = self.am1_re.search(gline)
                    # Start macro if there is a match, else not an AM, carry on.
                    if match:
                        self.app.log.debug("Starting macro. Line %d: %s" % (line_num, gline))
                        current_macro = match.group(1)
                        self.aperture_macros[current_macro] = ApertureMacro(name=current_macro)
                        if match.group(2):  # Append
                            self.aperture_macros[current_macro].append(match.group(2))
                        if match.group(3):  # Finish macro
                            # self.aperture_macros[current_macro].parse_content()
                            current_macro = None
                            self.app.log.debug("Macro complete in 1 line.")
                        continue
                else:  # Continue macro
                    self.app.log.debug("Continuing macro. Line %d." % line_num)
                    match = self.am2_re.search(gline)
                    if match:  # Finish macro
                        self.app.log.debug("End of macro. Line %d." % line_num)
                        self.aperture_macros[current_macro].append(match.group(1))
                        # self.aperture_macros[current_macro].parse_content()
                        current_macro = None
                    else:  # Append
                        self.aperture_macros[current_macro].append(gline)
                    continue

                # ################################################################
                # ##############   Aperture definitions %ADD...  #################
                # ################################################################
                match = self.ad_re.search(gline)
                if match:
                    # log.info("Found aperture definition. Line %d: %s" % (line_num, gline))
                    self.aperture_parse(match.group(1), match.group(2), match.group(3))
                    continue

                # ################################################################
                # ################  Operation code alone #########################
                # ###########   Operation code alone, usually just D03 (Flash) ###
                # self.opcode_re = re.compile(r'^D0?([123])\*$')
                # ################################################################
                match = self.opcode_re.search(gline)
                if match and current_aperture != "failure":
                    current_operation_code = int(match.group(1))
                    current_d = current_operation_code

                    if current_operation_code == 3:

                        # --- Buffered ---
                        try:
                            # self.app.log.debug("Bare op-code %d." % current_operation_code)
                            geo_dict = {}
                            flash = self.create_flash_geometry(
                                Point(current_x, current_y), self.tools[current_aperture],
                                self.steps_per_circle)

                            geo_dict['follow'] = Point([current_x, current_y])

                            if not flash.is_empty:
                                if self.app.options['gerber_simplification']:
                                    flash = flash.simplify(s_tol)

                                prepare(flash)
                                poly_buffer.append(flash)
                                if self.is_lpc is True:
                                    geo_dict['clear'] = flash
                                else:
                                    geo_dict['solid'] = flash

                                if current_aperture not in self.tools:
                                    self.tools[current_aperture] = {}

                                if 'geometry' not in self.tools[current_aperture]:
                                    self.tools[current_aperture]['geometry'] = []
                                self.tools[current_aperture]['geometry'].append(geo_dict)

                        except IndexError:
                            self.app.log.warning("Line %d: %s -> Nothing there to flash!" % (line_num, gline))

                    continue

                # ################################################################
                # ################  Tool/aperture change  ########################
                # ################  Example: D12*         ########################
                # self.tool_re = re.compile(r'^(?:G54)?D(\d\d+)\*$')
                # ################################################################
                match = self.tool_re.search(gline)
                if match:
                    current_aperture = int(match.group(1))

                    # self.app.log.debug("Line %d: Aperture change to (%s)" % (line_num, current_aperture))

                    # If the aperture value is zero then make it something quite small but with a non-zero value
                    # such that it can be processed by FlatCAM.
                    # But first test to see if the aperture type is "aperture macro". In that case
                    # we should not test for "size" key as it does not exist in this case.
                    if current_aperture in self.tools and self.tools[current_aperture]["type"] != "AM":
                        if self.tools[current_aperture]["size"] == 0:
                            self.tools[current_aperture]["size"] = 10 ** -self.decimals

                    # if the detected aperture is not detected already then it means that we have a
                    if current_aperture not in self.tools:
                        current_aperture = "failure"
                        self.defective_aperture_detected = True

                    # self.app.log.debug(self.tools[current_aperture])

                    # Take care of the current path with the previous tool
                    try:
                        path_length = len(path)
                    except TypeError:
                        path_length = 1

                    if path_length > 1:
                        if self.tools[last_path_aperture]["type"] == 'R':
                            # do nothing because 'R' type moving aperture is none at once
                            pass
                        else:
                            geo_dict = {}
                            geo_f = LineString(path)
                            prepare(geo_f)
                            if not geo_f.is_empty:
                                follow_buffer.append(geo_f)
                                geo_dict['follow'] = geo_f

                            # --- Buffered ----
                            width = self.tools[last_path_aperture]["size"]
                            geo_s = LineString(path).buffer(width / 1.999, int(self.steps_per_circle))
                            if self.app.options['gerber_simplification']:
                                geo_s = geo_s.simplify(s_tol)
                            prepare(geo_s)
                            if not geo_s.is_empty:
                                poly_buffer.append(geo_s)

                                if self.is_lpc is True:
                                    geo_dict['clear'] = geo_s
                                else:
                                    geo_dict['solid'] = geo_s

                            if last_path_aperture not in self.tools:
                                self.tools[last_path_aperture] = {}
                            if 'geometry' not in self.tools[last_path_aperture]:
                                self.tools[last_path_aperture]['geometry'] = []
                            self.tools[last_path_aperture]['geometry'].append(geo_dict)

                            path = [path[-1]]
                    continue

                # ################################################################
                # ################  G36* - Begin region   ########################
                # ################################################################
                if self.regionon_re.search(gline) and current_aperture != "failure":
                    try:
                        path_length = len(path)
                    except TypeError:
                        path_length = 1

                    if path_length > 1:
                        # Take care of what is left in the path

                        geo_dict = {}
                        geo_f = LineString(path)
                        if not geo_f.is_empty:
                            follow_buffer.append(geo_f)
                            geo_dict['follow'] = geo_f

                        # --- Buffered ----
                        width = self.tools[last_path_aperture]["size"]
                        geo_s = LineString(path).buffer(width / 1.999, int(self.steps_per_circle))
                        if not geo_s.is_valid:
                            self.app.log.warning(
                                "Found invalid Gerber geometry at line: %s. Fixing..." % str(line_num))
                            geo_s = geo_s.buffer(0.0000001, int(self.steps_per_circle))

                        if not geo_s.is_valid:
                            self.app.log.warning(
                                "Failed to fix the invalid Geometry found at line: %s" % str(line_num))
                        else:
                            if last_path_aperture not in self.tools:
                                self.tools[last_path_aperture] = {}
                            if 'geometry' not in self.tools[last_path_aperture]:
                                self.tools[last_path_aperture]['geometry'] = []
                            try:
                                for pol in geo_s:
                                    if not pol.is_empty:
                                        # is it possible that simplification creates an Empty Geometry ?????
                                        if self.app.options['gerber_simplification']:
                                            pol = pol.simplify(s_tol)

                                        prepare(pol)
                                        poly_buffer.append(pol)
                                        if self.is_lpc is True:
                                            geo_dict['clear'] = pol
                                        else:
                                            geo_dict['solid'] = pol

                                    if not pol.is_empty:
                                        self.tools[last_path_aperture]['geometry'].append(geo_dict)
                            except TypeError:
                                if not geo_s.is_empty:
                                    # is it possible that simplification creates an Empty Geometry ?????
                                    if self.app.options['gerber_simplification']:
                                        geo_s = geo_s.simplify(s_tol)

                                    prepare(geo_s)
                                    poly_buffer.append(geo_s)
                                    if self.is_lpc is True:
                                        geo_dict['clear'] = geo_s
                                    else:
                                        geo_dict['solid'] = geo_s

                                if not geo_s.is_empty:
                                    self.tools[last_path_aperture]['geometry'].append(geo_dict)

                        path = [path[-1]]

                    making_region = True
                    # flashes are not allowed inside regions
                    if current_operation_code == 3:
                        current_operation_code = 2
                    continue

                # ################################################################
                # ################  G37* - End region     ########################
                # ################################################################
                if self.regionoff_re.search(gline) and current_aperture != "failure":
                    making_region = False

                    if 0 not in self.tools:
                        self.tools[0] = {}
                        self.tools[0]['type'] = 'REG'
                        self.tools[0]['size'] = 0.0
                        self.tools[0]['geometry'] = []

                    # if D02 happened before G37 we now have a path with 1 element only; we have to add the current
                    # geo to the poly_buffer otherwise we loose it
                    if current_operation_code == 2:
                        try:
                            path_length = len(path)
                        except TypeError:
                            path_length = 1

                        if path_length == 1:
                            # this means that the geometry was prepared previously and we just need to add it
                            geo_dict = {}
                            if geo_f:
                                if not geo_f.is_empty:
                                    prepare(geo_f)
                                    follow_buffer.append(geo_f)
                                    geo_dict['follow'] = geo_f
                            if geo_s:
                                if not geo_s.is_empty:
                                    if self.app.options['gerber_simplification']:
                                        geo_s = geo_s.simplify(s_tol)

                                    if not geo_s.is_valid:
                                        print("Not valid: ", line_num)
                                    prepare(geo_s)
                                    poly_buffer.append(geo_s)
                                    if self.is_lpc is True:
                                        geo_dict['clear'] = geo_s
                                    else:
                                        geo_dict['solid'] = geo_s

                            if geo_s or geo_f:
                                self.tools[0]['geometry'].append(geo_dict)

                            path = [[current_x, current_y]]  # Start new path

                    # Only one path defines region?
                    # This can happen if D02 happened before G37 and
                    # is not and error.
                    try:
                        path_length = len(path)
                    except TypeError:
                        path_length = 1

                    if path_length < 3:
                        # print "ERROR: Path contains less than 3 points:"
                        # path = [[current_x, current_y]]
                        continue

                    # For Gerber regions, we may ignore an aperture that is None

                    # --- Buffered ---
                    geo_dict = {}
                    if current_aperture in self.tools:
                        # the following line breaks loading of Circuit Studio Gerber files
                        # buff_value = float(self.tools[current_aperture]['size']) / 2.0
                        # region_geo = Polygon(path).buffer(buff_value, int(self.steps_per_circle))
                        region_geo = Polygon(path)  # Sprint Layout Gerbers with ground fill are crashed with above
                    else:
                        region_geo = Polygon(path)

                    region_s = region_geo

                    if not region_s.is_empty:
                        if not region_s.is_valid:
                            self.app.log.warning(
                                "Found invalid Gerber geometry at line: %s. Fixing..." % str(line_num))
                            region_s = region_s.buffer(0.0000001, int(self.steps_per_circle))
                            region_s = flatten_shapely_geometry(region_s)

                            if not region_s:
                                self.app.log.warning(
                                    "Failed to fix the invalid Geometry found at line: %s" % str(line_num))
                            else:
                                for pol in region_s:
                                    # is it possible that simplification creates an Empty Geometry ?????
                                    if self.app.options['gerber_simplification']:
                                        pol = pol.simplify(s_tol)

                                    prepare(pol)
                                    pol_f = pol.exterior
                                    prepare(pol_f)
                                    if not pol_f.is_empty:
                                        follow_buffer.append(pol_f)
                                        geo_dict['follow'] = pol

                                    poly_buffer.append(pol)

                                    if self.is_lpc is True:
                                        geo_dict['clear'] = pol
                                    else:
                                        geo_dict['solid'] = pol

                                    if not pol.is_empty:
                                        self.tools[0]['geometry'].append(geo_dict)
                        else:
                            # is it possible that simplification creates an Empty Geometry ?????
                            if self.app.options['gerber_simplification']:
                                region_s = region_s.simplify(s_tol)

                            region_f = region_s.exterior
                            if not region_f.is_empty:
                                prepare(region_f)
                                follow_buffer.append(region_f)
                                geo_dict['follow'] = region_f

                            prepare(region_s)
                            poly_buffer.append(region_s)

                            if self.is_lpc is True:
                                geo_dict['clear'] = region_s
                            else:
                                geo_dict['solid'] = region_s

                            if not region_s.is_empty:
                                self.tools[0]['geometry'].append(geo_dict)

                    path = [[current_x, current_y]]  # Start new path
                    continue

                # ################################################################
                # ################  G01/2/3* - Interpolation mode change #########
                # ####  Can occur along with coordinates and operation code but ##
                # ####  sometimes by itself (handled here).  #####################
                # ####  Example: G01*                        #####################
                # ################################################################
                match = self.interp_re.search(gline)
                if match:
                    current_interpolation_mode = int(match.group(1))
                    continue

                # ################################################################
                # ######### G01 - Linear interpolation plus flashes  #############
                # ######### Operation code (D0x) missing is deprecated   #########
                # REGEX: r'^(?:G0?(1))?(?:X(-?\d+))?(?:Y(-?\d+))?(?:D0([123]))?\*$'
                # ################################################################
                match = self.lin_re.search(gline)
                if match and current_aperture != "failure":
                    # Dxx alone?
                    # if match.group(1) is None and match.group(2) is None and match.group(3) is None:
                    #     try:
                    #         current_operation_code = int(match.group(4))
                    #     except Exception:
                    #         pass  # A line with just * will match too.
                    #     continue
                    # NOTE: Letting it continue allows it to react to the
                    #       operation code.

                    # Parse coordinates
                    if match.group(2) is not None:
                        linear_x = parse_gerber_number(match.group(2),
                                                       self.int_digits, self.frac_digits, self.gerber_zeros)
                        current_x = linear_x
                    else:
                        linear_x = current_x
                    if match.group(3) is not None:
                        linear_y = parse_gerber_number(match.group(3),
                                                       self.int_digits, self.frac_digits, self.gerber_zeros)
                        current_y = linear_y
                    else:
                        linear_y = current_y

                    # Parse operation code
                    if match.group(4) is not None:
                        current_operation_code = int(match.group(4))

                        # Pen down: add segment
                    if current_operation_code == 1:
                        # if linear_x or linear_y are None, ignore those
                        if current_x is not None and current_y is not None:
                            # only add the point if it's a new one otherwise skip it (harder to process)
                            if path[-1] != [current_x, current_y]:
                                path.append([current_x, current_y])
                            elif len(path) == 1:
                                # it's a flash that is done by moving with pen up D2 and then just a pen down D1
                                # Reset path starting point
                                path = [[current_x, current_y]]

                                # treat the case when there is a flash inside a Gerber Region when the current_aperture
                                # is None
                                if current_aperture is not None:
                                    # --- BUFFERED ---
                                    # Draw the flash
                                    # this treats the case when we are storing geometry as paths
                                    geo_dict = {}
                                    geo_flash = Point([current_x, current_y])
                                    follow_buffer.append(geo_flash)
                                    geo_dict['follow'] = geo_flash

                                    # this treats the case when we are storing geometry as solids
                                    flash = self.create_flash_geometry(
                                        Point([current_x, current_y]),
                                        self.tools[current_aperture],
                                        self.steps_per_circle
                                    )
                                    if not flash.is_empty:
                                        if self.app.options['gerber_simplification']:
                                            flash = flash.simplify(s_tol)

                                        prepare(flash)
                                        poly_buffer.append(flash)

                                        if self.is_lpc is True:
                                            geo_dict['clear'] = flash
                                        else:
                                            geo_dict['solid'] = flash

                                    if current_aperture not in self.tools:
                                        self.tools[current_aperture] = {}
                                    if 'geometry' not in self.tools[current_aperture]:
                                        self.tools[current_aperture]['geometry'] = []
                                    self.tools[current_aperture]['geometry'].append(geo_dict)

                            if making_region is False:
                                # if the aperture is rectangle then add a rectangular shape having as parameters the
                                # coordinates of the start and end point and also the width and height
                                # of the 'R' aperture
                                try:
                                    if self.tools[current_aperture]["type"] == 'R':
                                        width = self.tools[current_aperture]['width']
                                        height = self.tools[current_aperture]['height']
                                        minx = min(path[0][0], path[1][0]) - width / 2
                                        maxx = max(path[0][0], path[1][0]) + width / 2
                                        miny = min(path[0][1], path[1][1]) - height / 2
                                        maxy = max(path[0][1], path[1][1]) + height / 2
                                        self.app.log.debug("Coords: %s - %s - %s - %s" % (minx, miny, maxx, maxy))

                                        geo_dict = {}
                                        geo_f = Point([current_x, current_y])
                                        prepare(geo_f)
                                        follow_buffer.append(geo_f)
                                        geo_dict['follow'] = geo_f

                                        geo_s = shply_box(minx, miny, maxx, maxy)
                                        if self.app.options['gerber_simplification']:
                                            geo_s = geo_s.simplify(s_tol)

                                        prepare(geo_s)
                                        poly_buffer.append(geo_s)

                                        if self.is_lpc is True:
                                            geo_dict['clear'] = geo_s
                                        else:
                                            geo_dict['solid'] = geo_s

                                        if current_aperture not in self.tools:
                                            self.tools[current_aperture] = {}
                                        if 'geometry' not in self.tools[current_aperture]:
                                            self.tools[current_aperture]['geometry'] = []
                                        self.tools[current_aperture]['geometry'].append(geo_dict)
                                except Exception:
                                    pass

                            if current_aperture != "failure":
                                last_path_aperture = current_aperture
                            # we do this for the case that a region is done without having defined any aperture
                            if last_path_aperture is None:
                                if 0 not in self.tools:
                                    self.tools[0] = {}
                                    self.tools[0]['type'] = 'REG'
                                    self.tools[0]['size'] = 0.0
                                    self.tools[0]['geometry'] = []
                                last_path_aperture = 0
                        else:
                            self.app.inform.emit('[WARNING] %s: %s' %
                                                 (_("Coordinates missing, line ignored"), str(gline)))
                            self.app.inform.emit('[WARNING_NOTCL] %s' %
                                                 _("GERBER file might be CORRUPT. Check the file !!!"))

                    elif current_operation_code == 2:
                        try:
                            path_length = len(path)
                        except TypeError:
                            path_length = 1

                        if path_length > 1:
                            geo_s = None

                            geo_dict = {}
                            # --- BUFFERED ---
                            # this treats the case when we are storing geometry as paths only
                            if making_region:
                                # we do this for the case that a region is done without having defined any aperture
                                if last_path_aperture is None:
                                    if 0 not in self.tools:
                                        self.tools[0] = {}
                                        self.tools[0]['type'] = 'REG'
                                        self.tools[0]['size'] = 0.0
                                        self.tools[0]['geometry'] = []
                                    last_path_aperture = 0
                                geo_f = Polygon()
                            else:
                                geo_f = LineString(path)

                            try:
                                if self.tools[last_path_aperture]["type"] != 'R':
                                    if not geo_f.is_empty:
                                        follow_buffer.append(geo_f)
                                        geo_dict['follow'] = geo_f
                            except Exception as e:
                                self.app.log.error("camlib.Gerber.parse_lines() --> %s" % str(e))
                                if not geo_f.is_empty:
                                    follow_buffer.append(geo_f)
                                    geo_dict['follow'] = geo_f

                            # this treats the case when we are storing geometry as solids
                            if making_region:
                                # we do this for the case that a region is done without having defined any aperture
                                if last_path_aperture is None:
                                    if 0 not in self.tools:
                                        self.tools[0] = {}
                                        self.tools[0]['type'] = 'REG'
                                        self.tools[0]['size'] = 0.0
                                        self.tools[0]['geometry'] = []
                                    last_path_aperture = 0

                                try:
                                    geo_s = Polygon(path)
                                except ValueError:
                                    self.app.log.warning("Problem %s %s" % (gline, line_num))
                                    self.app.inform.emit('[ERROR] %s: %s' %
                                                         (_("Region does not have enough points. "
                                                            "File will be processed but there are parser errors. "
                                                            "Line number"), str(line_num)))
                            else:
                                if last_path_aperture is None:
                                    self.app.log.warning("No aperture defined for curent path. (%d)" % line_num)
                                # TODO: this may (should) fail
                                width = self.tools[last_path_aperture]["size"]
                                geo_s = LineString(path).buffer(width / 1.999, int(self.steps_per_circle))

                            try:
                                if self.tools[last_path_aperture]["type"] != 'R':
                                    if not geo_s.is_empty:
                                        if self.app.options['gerber_simplification']:
                                            geo_s = geo_s.simplify(s_tol)

                                        prepare(geo_s)
                                        poly_buffer.append(geo_s)

                                        if self.is_lpc is True:
                                            geo_dict['clear'] = geo_s
                                        else:
                                            geo_dict['solid'] = geo_s
                            except Exception as e:
                                self.app.log.error("camlib.Gerber.parse_lines() --> %s" % str(e))
                                if self.app.options['gerber_simplification']:
                                    geo_s = geo_s.simplify(s_tol)

                                prepare(geo_s)
                                poly_buffer.append(geo_s)

                                if self.is_lpc is True:
                                    geo_dict['clear'] = geo_s
                                else:
                                    geo_dict['solid'] = geo_s

                            if last_path_aperture not in self.tools:
                                self.tools[last_path_aperture] = {}
                            if 'geometry' not in self.tools[last_path_aperture]:
                                self.tools[last_path_aperture]['geometry'] = []
                            self.tools[last_path_aperture]['geometry'].append(geo_dict)

                        # if linear_x or linear_y are None, ignore those
                        if linear_x is not None and linear_y is not None:
                            path = [[linear_x, linear_y]]  # Start new path
                        else:
                            self.app.inform.emit('[WARNING] %s: %s' %
                                                 (_("Coordinates missing, line ignored"), str(gline)))
                            self.app.inform.emit('[WARNING_NOTCL] %s' %
                                                 _("GERBER file might be CORRUPT. Check the file !!!"))

                    # Flash
                    # Not allowed in region mode.
                    elif current_operation_code == 3:

                        # Create path draw so far.
                        try:
                            path_length = len(path)
                        except TypeError:
                            path_length = 1

                        if path_length > 1:
                            # --- Buffered ----
                            geo_dict = {}

                            # this treats the case when we are storing geometry as paths
                            geo_f = LineString(path)
                            if not geo_f.is_empty:
                                try:
                                    if self.tools[last_path_aperture]["type"] != 'R':
                                        follow_buffer.append(geo_f)
                                        geo_dict['follow'] = geo_f
                                except Exception as e:
                                    self.app.log.error("camlib.Gerber.parse_lines() --> G01 match D03 --> %s" % str(e))
                                    follow_buffer.append(geo_f)
                                    geo_dict['follow'] = geo_f

                            # this treats the case when we are storing geometry as solids
                            width = self.tools[last_path_aperture]["size"]
                            geo_s = LineString(path).buffer(width / 1.999, int(self.steps_per_circle))
                            if not geo_s.is_empty:
                                try:
                                    if self.tools[last_path_aperture]["type"] != 'R':
                                        if self.app.options['gerber_simplification']:
                                            geo_s = geo_s.simplify(s_tol)

                                        prepare(geo_s)
                                        poly_buffer.append(geo_s)

                                        if self.is_lpc is True:
                                            geo_dict['clear'] = geo_s
                                        else:
                                            geo_dict['solid'] = geo_s
                                except Exception:
                                    if self.app.options['gerber_simplification']:
                                        geo_s = geo_s.simplify(s_tol)

                                    prepare(geo_s)
                                    poly_buffer.append(geo_s)

                                    if self.is_lpc is True:
                                        geo_dict['clear'] = geo_s
                                    else:
                                        geo_dict['solid'] = geo_s

                            if last_path_aperture not in self.tools:
                                self.tools[last_path_aperture] = {}
                            if 'geometry' not in self.tools[last_path_aperture]:
                                self.tools[last_path_aperture]['geometry'] = []
                            self.tools[last_path_aperture]['geometry'].append(geo_dict)

                        # Reset path starting point
                        path = [[linear_x, linear_y]]

                        # --- BUFFERED ---
                        # Draw the flash
                        # this treats the case when we are storing geometry as paths

                        geo_dict = {}
                        geo_flash = Point([linear_x, linear_y])
                        prepare(geo_flash)
                        follow_buffer.append(geo_flash)
                        geo_dict['follow'] = geo_flash

                        # this treats the case when we are storing geometry as solids
                        flash = self.create_flash_geometry(
                            Point([linear_x, linear_y]),
                            self.tools[current_aperture],
                            self.steps_per_circle
                        )

                        if not flash.is_empty:
                            if self.app.options['gerber_simplification']:
                                flash = flash.simplify(s_tol)

                            prepare(flash)
                            poly_buffer.append(flash)

                            if self.is_lpc is True:
                                geo_dict['clear'] = flash
                            else:
                                geo_dict['solid'] = flash

                        if current_aperture not in self.tools:
                            self.tools[current_aperture] = {}
                        if 'geometry' not in self.tools[current_aperture]:
                            self.tools[current_aperture]['geometry'] = []
                        self.tools[current_aperture]['geometry'].append(geo_dict)

                    # maybe those lines are not exactly needed but it is easier to read the program as those coordinates
                    # are used in case that circular interpolation is encountered within the Gerber file
                    current_x = linear_x
                    current_y = linear_y

                    # self.app.log.debug("Line_number=%3s X=%s Y=%s (%s)" % (line_num, linear_x, linear_y, gline))
                    continue

                # ################################################################
                # ######### G74/75* - Single or multiple quadrant arcs  ##########
                # ################################################################
                match = self.quad_re.search(gline)
                if match:
                    if match.group(1) == '4':
                        quadrant_mode = 'SINGLE'
                    else:
                        quadrant_mode = 'MULTI'
                    continue

                # ################################################################
                # ######### G02/3 - Circular interpolation   #####################
                # ######### 2-clockwise, 3-counterclockwise  #####################
                # ######### Ex. format: G03 X0 Y50 I-50 J0 where the     #########
                # ######### X, Y coords are the coords of the End Point  #########
                # ################################################################
                match = self.circ_re.search(gline)
                if match and current_aperture != "failure":
                    arcdir = [None, None, "cw", "ccw"]

                    mode, circular_x, circular_y, i, j, d = match.groups()

                    try:
                        circular_x = parse_gerber_number(circular_x,
                                                         self.int_digits, self.frac_digits, self.gerber_zeros)
                    except Exception:
                        circular_x = current_x

                    try:
                        circular_y = parse_gerber_number(circular_y,
                                                         self.int_digits, self.frac_digits, self.gerber_zeros)
                    except Exception:
                        circular_y = current_y

                    # According to Gerber specification i and j are not modal, which means that when i or j are missing,
                    # they are to be interpreted as being zero
                    try:
                        i = parse_gerber_number(i, self.int_digits, self.frac_digits, self.gerber_zeros)
                    except Exception:
                        i = 0

                    try:
                        j = parse_gerber_number(j, self.int_digits, self.frac_digits, self.gerber_zeros)
                    except Exception:
                        j = 0

                    if quadrant_mode is None:
                        self.app.log.error(
                            "Found arc without preceding quadrant specification G74 or G75. (%d)" % line_num)
                        self.app.log.error(gline)
                        continue

                    if mode is None and current_interpolation_mode not in [2, 3]:
                        self.app.log.error("Found arc without circular interpolation mode defined. (%d)" % line_num)
                        self.app.log.error(gline)
                        continue
                    elif mode is not None:
                        current_interpolation_mode = int(mode)

                    # Set operation code if provided
                    if d is not None:
                        current_operation_code = int(d)

                    # Nothing created! Pen Up.
                    if current_operation_code == 2:
                        self.app.log.warning("Arc with D2. (%d)" % line_num)
                        try:
                            path_length = len(path)
                        except TypeError:
                            path_length = 1

                        if path_length > 1:
                            geo_dict = {}

                            if last_path_aperture is None:
                                self.app.log.warning("No aperture defined for curent path. (%d)" % line_num)

                            # --- BUFFERED ---
                            width = self.tools[last_path_aperture]["size"]

                            # this treats the case when we are storing geometry as paths
                            geo_f = LineString(path)
                            if not geo_f.is_empty:
                                prepare(geo_f)
                                follow_buffer.append(geo_f)
                                geo_dict['follow'] = geo_f

                            # this treats the case when we are storing geometry as solids
                            buffered = LineString(path).buffer(width / 1.999, int(self.steps_per_circle))
                            if not buffered.is_empty:
                                if self.app.options['gerber_simplification']:
                                    buffered = buffered.simplify(s_tol)

                                prepare(buffered)
                                poly_buffer.append(buffered)

                                if self.is_lpc is True:
                                    geo_dict['clear'] = buffered
                                else:
                                    geo_dict['solid'] = buffered

                            if last_path_aperture not in self.tools:
                                self.tools[last_path_aperture] = {}
                            if 'geometry' not in self.tools[last_path_aperture]:
                                self.tools[last_path_aperture]['geometry'] = []
                            self.tools[last_path_aperture]['geometry'].append(geo_dict)

                        current_x = circular_x
                        current_y = circular_y
                        path = [[current_x, current_y]]  # Start new path
                        continue

                    # Flash should not happen here
                    if current_operation_code == 3:
                        self.app.log.error("Trying to flash within arc. (%d)" % line_num)
                        continue

                    if quadrant_mode == 'MULTI':
                        center = [i + current_x, j + current_y]
                        radius = np.sqrt(i ** 2 + j ** 2)
                        start = np.arctan2(-j, -i)  # Start angle
                        # Numerical errors might prevent start == stop therefore
                        # we check ahead of time. This should result in a
                        # 360 degree arc.
                        if current_x == circular_x and current_y == circular_y:
                            stop = start
                        else:
                            stop = np.arctan2(-center[1] + circular_y, -center[0] + circular_x)  # Stop angle

                        this_arc = arc(center, radius, start, stop,
                                       arcdir[current_interpolation_mode],
                                       self.steps_per_circle)

                        # The last point in the computed arc can have
                        # numerical errors. The exact final point is the
                        # specified (x, y). Replace.
                        this_arc[-1] = (circular_x, circular_y)

                        # Last point in path is current point
                        # current_x = this_arc[-1][0]
                        # current_y = this_arc[-1][1]
                        current_x, current_y = circular_x, circular_y

                        # Append
                        path += this_arc
                        last_path_aperture = current_aperture

                        continue

                    if quadrant_mode == 'SINGLE':

                        center_candidates = [
                            [i + current_x, j + current_y],
                            [-i + current_x, j + current_y],
                            [i + current_x, -j + current_y],
                            [-i + current_x, -j + current_y]
                        ]

                        valid = False
                        # self.app.log.debug("I: %f  J: %f" % (i, j))
                        for center in center_candidates:
                            radius = np.sqrt(i ** 2 + j ** 2)

                            # Make sure radius to start is the same as radius to end.
                            radius2 = np.sqrt((center[0] - circular_x) ** 2 + (center[1] - circular_y) ** 2)
                            if radius2 < radius * 0.95 or radius2 > radius * 1.05:
                                continue  # Not a valid center.

                            # Correct i and j and continue as with multi-quadrant.
                            i = center[0] - current_x
                            j = center[1] - current_y

                            start = np.arctan2(-j, -i)  # Start angle
                            stop = np.arctan2(-center[1] + circular_y, -center[0] + circular_x)  # Stop angle
                            angle = abs(arc_angle(start, stop, arcdir[current_interpolation_mode]))
                            # self.app.log.debug("ARC START: %f, %f  CENTER: %f, %f  STOP: %f, %f" %
                            #           (current_x, current_y, center[0], center[1], circular_x, circular_y))
                            # self.app.log.debug("START Ang: %f, STOP Ang: %f, DIR: %s, ABS: %.12f <= %.12f: %s" %
                            #           (start * 180 / np.pi, stop * 180 / np.pi, arcdir[current_interpolation_mode],
                            #            angle * 180 / np.pi, np.pi / 2 * 180 / np.pi, angle <= (np.pi + 1e-6) / 2))

                            if angle <= (np.pi + 1e-6) / 2:
                                # self.app.log.debug("########## ACCEPTING ARC ############")
                                this_arc = arc(center, radius, start, stop,
                                               arcdir[current_interpolation_mode],
                                               self.steps_per_circle)

                                # Replace with exact values
                                this_arc[-1] = (circular_x, circular_y)

                                # current_x = this_arc[-1][0]
                                # current_y = this_arc[-1][1]
                                current_x, current_y = circular_x, circular_y

                                path += this_arc
                                last_path_aperture = current_aperture
                                valid = True
                                break

                        if valid:
                            continue
                        else:
                            self.app.log.warning("Invalid arc in line %d." % line_num)

                # ################################################################
                # ######### EOF - END OF FILE ####################################
                # ################################################################
                match = self.eof_re.search(gline)
                if match:
                    continue

                # ################################################################
                # ######### Line did not match any pattern. Warn user.  ##########
                # ################################################################
                self.app.log.warning("Line ignored (%d): %s" % (line_num, gline))
                # provide the app with a way to process the GUI events when in a blocking loop
                QtWidgets.QApplication.processEvents()

            try:
                path_length = len(path)
            except TypeError:
                path_length = 1

            if path_length > 1:
                # In case that G01 (moving) aperture is rectangular, there is no need to still create
                # another geo since we already created a shapely box using the start and end coordinates found in
                # path variable. We do it only for other apertures than 'R' type
                if self.tools[last_path_aperture]["type"] == 'R':
                    pass
                else:
                    # EOF, create shapely LineString if something still in path
                    # ## --- Buffered ---

                    geo_dict = {}
                    # this treats the case when we are storing geometry as paths
                    geo_f = LineString(path)
                    if not geo_f.is_empty:
                        prepare(geo_f)
                        follow_buffer.append(geo_f)
                        geo_dict['follow'] = geo_f

                    # this treats the case when we are storing geometry as solids
                    width = self.tools[last_path_aperture]["size"]
                    geo_s = LineString(path).buffer(width / 1.999, int(self.steps_per_circle))
                    if not geo_s.is_empty:
                        if self.app.options['gerber_simplification']:
                            geo_s = geo_s.simplify(s_tol)

                        prepare(geo_s)
                        poly_buffer.append(geo_s)

                        if self.is_lpc is True:
                            geo_dict['clear'] = geo_s
                        else:
                            geo_dict['solid'] = geo_s

                    if last_path_aperture not in self.tools:
                        self.tools[last_path_aperture] = {}
                    if 'geometry' not in self.tools[last_path_aperture]:
                        self.tools[last_path_aperture]['geometry'] = []
                    self.tools[last_path_aperture]['geometry'].append(geo_dict)

            # ##########################################################################################################
            #   Creating the FINAL GEOMETRY
            # ##########################################################################################################
            # --- Apply buffer ---
            # this treats the case when we are storing geometry as paths
            self.follow_geometry = flatten_shapely_geometry(follow_buffer)

            # this treats the case when we are storing geometry as solids
            try:
                buff_length = len(poly_buffer)
            except TypeError:
                buff_length = 1

            if isinstance(self.solid_geometry, MultiPolygon):
                sol_geo_length = len(self.solid_geometry.geoms)
            elif isinstance(self.solid_geometry, list):
                sol_geo_length = len(self.solid_geometry)
            else:
                sol_geo_length = 1

            try:
                if buff_length == 0 and sol_geo_length in [0, 1] and self.solid_geometry.area == 0:
                    self.app.log.error("Object is not Gerber file or empty. Aborting Object creation.")
                    return 'fail'
            except TypeError as e:
                self.app.log.error("Object is not Gerber file or empty. Aborting Object creation. %s" % str(e))
                return 'fail'

            self.app.log.warning("Joining %d polygons." % buff_length)
            self.app.inform.emit('%s: %d.' % (_("Gerber processing. Joining polygons"), buff_length))

            if self.use_buffer_for_union:
                self.app.log.debug("Union by buffer...")

                new_poly = MultiPolygon(poly_buffer)
                if self.app.options["gerber_buffering"] == 'full':
                    new_poly = new_poly.buffer(0.00000001)
                    new_poly = new_poly.buffer(-0.00000001)
                    self.app.log.warning("Union(buffer) done.")

            else:
                self.app.log.debug("Union by union()...")
                new_poly = unary_union(poly_buffer)
                new_poly = new_poly.buffer(0, int(self.steps_per_circle))
                self.app.log.warning("Union done.")

            # #########################################################################################################
            prepare(new_poly)
            # #########################################################################################################

            if current_polarity == 'D':
                self.app.inform.emit('%s' % _("Gerber processing. Applying Gerber polarity."))
                if new_poly.is_valid:
                    self.solid_geometry = self.solid_geometry.union(new_poly)
                else:
                    # I do this so whenever the parsed geometry of the file is not valid (intersections) it is still
                    # loaded. Instead of applying a union I add to a list of polygons.
                    final_poly = []
                    try:
                        for poly in new_poly:
                            final_poly.append(poly)
                    except TypeError:
                        final_poly.append(new_poly)

                    try:
                        for poly in self.solid_geometry:
                            final_poly.append(poly)
                    except TypeError:
                        final_poly.append(self.solid_geometry)

                    self.solid_geometry = final_poly

                # FIX for issue #347 - Sprint Layout generate Gerber files when the copper pour is enabled
                # it use a filled bounding box polygon to which add clear polygons (negative) to isolate the copper
                # features
                if self.app.options['gerber_extra_buffering']:
                    candidate_geo = []
                    if isinstance(self.solid_geometry, MultiPolygon):
                        geo_to_buff = self.solid_geometry.geoms
                    else:
                        geo_to_buff = self.solid_geometry
                    try:
                        for p in geo_to_buff:
                            candidate_geo.append(p.buffer(-0.0000001))
                    except TypeError:
                        candidate_geo.append(geo_to_buff.buffer(-0.0000001))
                    self.solid_geometry = candidate_geo

            else:
                self.solid_geometry = self.solid_geometry.difference(new_poly)

            # flatten the solid geometry
            self.solid_geometry = flatten_shapely_geometry(self.solid_geometry)

            # import time
            # start = time.time()
            # #########################################################################################################
            prepare(self.solid_geometry)
            # #########################################################################################################
            # print(f"Time elapsed: {time.time() - start}; Is prepared? {is_prepared(self.solid_geometry)}")

            if self.app.options['gerber_clean_apertures']:
                # clean the Gerber file of apertures with no geometry
                for apid, apvalue in list(self.tools.items()):
                    if 'geometry' not in apvalue:
                        self.tools.pop(apid)

            # init this for the following operations
            self.conversion_done = False

            if self.defective_aperture_detected:
                return "defective"
        except Exception as err:
            ex_type, ex, tb = sys.exc_info()
            traceback.print_tb(tb)
            # print traceback.format_exc()

            self.app.log.error("Gerber PARSING FAILED. Line %d: %s" % (line_num, gline))
            self.app.log.error(str(traceback.format_exc()))

            loc = '%s #%d %s: %s\n' % (_("Gerber Line"), line_num, _("Gerber Line Content"), gline) + repr(err)
            self.app.inform.emit('[ERROR] %s\n%s:' % (_("Gerber Parser ERROR"), loc))
            return 'fail'

        if is_excellon_gx2 is True:
            return 'drill'

    def create_flash_geometry(self, location, aperture, steps_per_circle=None):

        # self.app.log.debug('Flashing @%s, Aperture: %s' % (location, aperture))

        if type(location) == list:
            location = Point(location)

        if aperture['type'] == 'C':  # Circles
            return location.buffer(aperture['size'] / 2, int(steps_per_circle))

        if aperture['type'] == 'R':  # Rectangles
            loc = location.coords[0]
            width = aperture['width']
            height = aperture['height']
            minx = loc[0] - width / 2
            maxx = loc[0] + width / 2
            miny = loc[1] - height / 2
            maxy = loc[1] + height / 2
            return shply_box(minx, miny, maxx, maxy).buffer(0.0000001)

        if aperture['type'] == 'O':  # Obround
            loc = location.coords[0]
            width = aperture['width']
            height = aperture['height']
            if width > height:
                p1 = Point(loc[0] + 0.5 * (width - height), loc[1])
                p2 = Point(loc[0] - 0.5 * (width - height), loc[1])
                c1 = p1.buffer(height * 0.5, int(steps_per_circle))
                c2 = p2.buffer(height * 0.5, int(steps_per_circle))
            else:
                p1 = Point(loc[0], loc[1] + 0.5 * (height - width))
                p2 = Point(loc[0], loc[1] - 0.5 * (height - width))
                c1 = p1.buffer(width * 0.5, int(steps_per_circle))
                c2 = p2.buffer(width * 0.5, int(steps_per_circle))
            return unary_union([c1, c2]).convex_hull

        if aperture['type'] == 'P':  # Regular polygon
            loc = location.coords[0]
            diam = aperture['diam']
            n_vertices = aperture['nVertices']
            points = []
            for i in range(0, n_vertices):
                x = loc[0] + 0.5 * diam * (np.cos(2 * np.pi * i / n_vertices))
                y = loc[1] + 0.5 * diam * (np.sin(2 * np.pi * i / n_vertices))
                points.append((x, y))
            ply = Polygon(points)
            if 'rotation' in aperture:
                ply = affinity.rotate(ply, aperture['rotation'])
            return ply

        if aperture['type'] == 'AM':  # Aperture Macro
            loc = location.coords[0]
            flash_geo = aperture['macro'].make_geometry(aperture['modifiers'])
            if flash_geo.is_empty:
                self.app.log.warning("Empty geometry for Aperture Macro: %s" % str(aperture['macro'].name))
            return affinity.translate(flash_geo, xoff=loc[0], yoff=loc[1])

        self.app.log.warning("Unknown aperture type: %s" % aperture['type'])
        return None

    def create_geometry(self):
        """
        Geometry from a Gerber file is made up entirely of polygons.
        Every stroke (linear or circular) has an aperture which gives
        it thickness. Additionally, aperture strokes have non-zero area,
        and regions naturally do as well.

        :rtype : None
        :return: None
        """
        pass
        # self.buffer_paths()
        #
        # self.fix_regions()
        #
        # self.do_flashes()
        #
        # self.solid_geometry = unary_union(self.buffered_paths +
        #                                      [poly['polygon'] for poly in self.regions] +
        #                                      self.flash_geometry)

    def get_bounding_box(self, margin=0.0, rounded=False):
        """
        Creates and returns a rectangular polygon bounding at a distance of
        margin from the object's ``solid_geometry``. If margin > 0, the polygon
        can optionally have rounded corners of radius equal to margin.

        :param margin: Distance to enlarge the rectangular bounding
         box in both positive and negative, x and y axes.
        :type margin: float
        :param rounded: Wether or not to have rounded corners.
        :type rounded: bool
        :return: The bounding box.
        :rtype: Shapely.Polygon
        """

        bbox = self.solid_geometry.envelope.buffer(margin)
        if not rounded:
            bbox = bbox.envelope
        return bbox

    def bounds(self, flatten=None):
        """
        Returns coordinates of rectangular bounds
        of Gerber geometry: (xmin, ymin, xmax, ymax).

        :param flatten:     Not used, it is here for compatibility with base class method
        :return:            None
        """

        self.app.log.debug("parseGerber.Gerber.bounds()")

        if self.solid_geometry is None:
            self.app.log.debug("solid_geometry is None")
            return 0, 0, 0, 0

        def bounds_rec(obj):
            if type(obj) is list and type(obj) is not MultiPolygon:
                minx = np.Inf
                miny = np.Inf
                maxx = -np.Inf
                maxy = -np.Inf

                for k in obj:
                    if type(k) is dict:
                        for key in k:
                            minx_, miny_, maxx_, maxy_ = bounds_rec(k[key])
                            minx = min(minx, minx_)
                            miny = min(miny, miny_)
                            maxx = max(maxx, maxx_)
                            maxy = max(maxy, maxy_)
                    else:
                        if not k.is_empty:
                            try:
                                minx_, miny_, maxx_, maxy_ = bounds_rec(k)
                            except Exception as e:
                                self.app.log.error("camlib.Gerber.bounds() --> %s" % str(e))
                                return

                            minx = min(minx, minx_)
                            miny = min(miny, miny_)
                            maxx = max(maxx, maxx_)
                            maxy = max(maxy, maxy_)
                return minx, miny, maxx, maxy
            else:
                # it's a Shapely object, return it's bounds
                return obj.bounds

        bounds_coords = bounds_rec(self.solid_geometry)
        return bounds_coords

    def convert_units(self, obj_units):
        """
        Converts the units of the object to ``units`` by scaling all
        the geometry appropriately. This call ``scale()``. Don't call
        it again in descendants.

        :param obj_units:   "IN" or "MM"
        :type obj_units:    str
        :return:            Scaling factor resulting from unit change.
        :rtype:             float
        """

        if obj_units.upper() == self.units.upper():
            self.app.log.debug("parseGerber.Gerber.convert_units() --> Factor: 1")
            return 1.0

        if obj_units.upper() == "MM":
            factor = 25.4
            self.app.log.debug("parseGerber.Gerber.convert_units() --> Factor: %s" % str(factor))
        elif obj_units.upper() == "IN":
            factor = 1 / 25.4
            self.app.log.debug("parseGerber.Gerber.convert_units() --> Factor: %s" % str(factor))
        else:
            self.app.log.error("Unsupported units: %s" % str(obj_units))
            self.app.log.debug("parseGerber.Gerber.convert_units() --> Factor: 1")
            return 1.0

        self.units = obj_units
        self.file_units_factor = factor
        self.scale(factor, factor)
        return factor

    def import_svg(self, filename, object_type='gerber', flip=True, units=None):
        """
        Imports shapes from an SVG file into the object's geometry.

        :param filename:        Path to the SVG file.
        :type filename:         str
        :param object_type:     parameter passed further along
        :param flip:            Flip the vertically.
        :type flip:             bool
        :param units:           FlatCAM units
        :return: None
        """

        self.app.log.debug("appParsers.ParseGerber.Gerber.import_svg()")

        # Parse into list of shapely objects
        svg_tree = ET.parse(filename)
        svg_root = svg_tree.getroot()

        # Change origin to bottom left
        # h = float(svg_root.get('height'))
        # w = float(svg_root.get('width'))
        h = svgparselength(svg_root.get('height'))[0]  # TODO: No units support yet

        units = self.app.app_units if units is None else units
        res = self.app.options['gerber_circle_steps']
        factor = svgparse_viewbox(svg_root)
        geos = getsvggeo(svg_root, 'gerber', units=units, res=res, factor=factor, app=self.app)

        self.app.log.debug("appParsers.ParseGerber.Gerber.import_svg(). Finished parsing the SVG geometry.")

        if flip:
            geos = [affinity.translate(affinity.scale(g, 1.0, -1.0, origin=(0, 0)), yoff=h) for g in geos]
            self.app.log.debug("appParsers.ParseGerber.Gerber.import_svg(). SVG geometry was flipped.")

        # Add to object
        if self.solid_geometry is None:
            self.solid_geometry = []

        # if type(self.solid_geometry) == list:
        #     if type(geos) == list:
        #         self.solid_geometry += geos
        #     else:
        #         self.solid_geometry.append(geos)
        # else:  # It's shapely geometry
        #     self.solid_geometry = [self.solid_geometry, geos]

        if type(geos) == list:
            # HACK for importing QRCODE exported by FlatCAM
            try:
                geos_length = len(geos)
            except TypeError:
                geos_length = 1

            if geos_length == 1:
                geo_qrcode = [Polygon(geos[0].exterior)]
                for i_el in geos[0].interiors:
                    geo_qrcode.append(Polygon(i_el).buffer(0, resolution=res))
                geos = [poly for poly in geo_qrcode]

            if type(self.solid_geometry) == list:
                self.solid_geometry += geos
            else:
                geos.append(self.solid_geometry)
                self.solid_geometry = geos
        else:
            if type(self.solid_geometry) == list:
                self.solid_geometry.append(geos)
            else:
                self.solid_geometry = [self.solid_geometry, geos]

        # flatten the self.solid_geometry list for import_svg() to import SVG as Gerber
        self.solid_geometry = flatten_shapely_geometry(self.solid_geometry)
        if 0 not in self.tools:
            self.tools[0] = {
                'type':         'REG',
                'size':         0.0,
                'geometry':     []
            }

        for pol in self.solid_geometry:
            prepare(pol)
            new_el = {'solid': pol, 'follow': LineString(pol.exterior.coords)}
            self.tools[0]['geometry'].append(new_el)

    def import_dxf_as_gerber(self, filename, units='MM'):
        """
        Imports shapes from an DXF file into the Gerber object geometry.

        :param filename:    Path to the DXF file.
        :type filename:     str
        :param units:       Application units
        :return: None
        """

        self.app.log.debug("Parsing DXF file geometry into a Gerber object geometry.")

        self.multigeo = True

        # Parse into list of shapely objects
        dxf = ezdxf.readfile(filename)
        geos = getdxfgeo(dxf)

        # trying to optimize the resulting geometry by merging contiguous lines
        geos = list(self.flatten_list(geos))
        geos_polys = []
        geos_lines = []
        for g in geos:
            if isinstance(g, (Polygon, MultiPolygon)):
                geos_polys.append(g)
            else:
                geos_lines.append(g)

        merged_lines = linemerge(geos_lines)
        geos = geos_polys

        try:
            w_geo = merged_lines.geoms if isinstance(merged_lines, MultiLineString) else merged_lines
            for ml in w_geo:
                geos.append(ml)
        except TypeError:
            geos.append(merged_lines)

        # Add to object
        if self.solid_geometry is None:
            self.solid_geometry = []

        if type(self.solid_geometry) is list:
            if type(geos) is list:
                self.solid_geometry += geos
            else:
                self.solid_geometry.append(geos)
        else:  # It's shapely geometry
            self.solid_geometry = [self.solid_geometry, geos]

        # flatten the self.solid_geometry list for import_dxf() to import DXF as Gerber
        flat_geo = list(self.flatten_list(self.solid_geometry))
        if flat_geo:
            self.solid_geometry = unary_union(flat_geo)
            prepare(self.solid_geometry)
            self.follow_geometry = self.solid_geometry
        else:
            return "fail"

        # create the self.tools data structure
        if 0 not in self.tools:
            self.tools[0] = {
                'type': 'REG',
                'size': 0.0,
                'geometry': []
            }

        for pol in flat_geo:
            new_el = {'solid': pol, 'follow': pol}
            self.tools[0]['geometry'].append(new_el)

    def scale(self, xfactor, yfactor=None, point=None):
        """
        Scales the objects' geometry on the XY plane by a given factor.
        These are:

        * ``buffered_paths``
        * ``flash_geometry``
        * ``solid_geometry``
        * ``regions``

        NOTE:
        Does not modify the data used to create these elements. If these
        are recreated, the scaling will be lost. This behavior was modified
        because of the complexity reached in this class.

        :param xfactor: Number by which to scale on X axis.
        :type xfactor: float
        :param yfactor: Number by which to scale on Y axis.
        :type yfactor: float
        :param point: reference point for scaling operation
        :rtype : None
        """
        self.app.log.debug("parseGerber.Gerber.scale()")

        try:
            xfactor = float(xfactor)
        except Exception:
            self.app.inform.emit('[ERROR_NOTCL] %s' %
                                 _("Scale factor has to be a number: integer or float."))
            return

        if yfactor is None:
            yfactor = xfactor
        else:
            try:
                yfactor = float(yfactor)
            except Exception:
                self.app.inform.emit('[ERROR_NOTCL] %s' %
                                     _("Scale factor has to be a number: integer or float."))
                return

        if xfactor == 0 and yfactor == 0:
            return

        if point is None:
            px = 0
            py = 0
        else:
            px, py = point

        # variables to display the percentage of work done
        self.geo_len = 0
        try:
            if isinstance(self.solid_geometry, MultiPolygon):
                self.geo_len = len(self.solid_geometry.geoms)
            else:
                self.geo_len = len(self.solid_geometry)
        except TypeError:
            self.geo_len = 1

        self.old_disp_number = 0
        self.el_count = 0

        def scale_geom(obj):
            if type(obj) is list:
                new_obj = []
                for g in obj:
                    new_obj.append(scale_geom(g))
                return new_obj
            else:
                try:
                    self.el_count += 1
                    disp_number = int(np.interp(self.el_count, [0, self.geo_len], [0, 99]))
                    if self.old_disp_number < disp_number <= 100:
                        self.app.proc_container.update_view_text(' %d%%' % disp_number)
                        self.old_disp_number = disp_number

                    return affinity.scale(obj, xfactor, yfactor, origin=(px, py))
                except AttributeError:
                    return obj

        self.solid_geometry = scale_geom(self.solid_geometry)
        self.follow_geometry = scale_geom(self.follow_geometry)

        # we need to scale the geometry stored in the Gerber apertures, too
        try:
            for apid in self.tools:
                new_geometry = []
                if 'geometry' in self.tools[apid]:
                    for geo_el in self.tools[apid]['geometry']:
                        new_geo_el = {}
                        if 'solid' in geo_el:
                            new_geo_el['solid'] = scale_geom(geo_el['solid'])
                        if 'follow' in geo_el:
                            new_geo_el['follow'] = scale_geom(geo_el['follow'])
                        if 'clear' in geo_el:
                            new_geo_el['clear'] = scale_geom(geo_el['clear'])
                        new_geometry.append(new_geo_el)

                self.tools[apid]['geometry'] = deepcopy(new_geometry)

                try:
                    if str(self.tools[apid]['type']) == 'R' or str(self.tools[apid]['type']) == 'O':
                        self.tools[apid]['width'] *= xfactor
                        self.tools[apid]['height'] *= xfactor
                    elif str(self.tools[apid]['type']) == 'P':
                        self.tools[apid]['diam'] *= xfactor
                        self.tools[apid]['nVertices'] *= xfactor
                except KeyError:
                    pass

                try:
                    if self.tools[apid]['size'] is not None:
                        self.tools[apid]['size'] = float(self.tools[apid]['size'] * xfactor)
                except KeyError:
                    pass

        except Exception as e:
            self.app.log.error('ParseGerber.Gerber.scale() Exception --> %s' % str(e))
            return 'fail'

        self.app.inform.emit('[success] %s' % _("Done."))
        self.app.proc_container.new_text = ''

        # ## solid_geometry ???
        #  It's a cascaded union of objects.
        # self.solid_geometry = affinity.scale(self.solid_geometry, factor,
        #                                      factor, origin=(0, 0))

        # # Now buffered_paths, flash_geometry and solid_geometry
        # self.create_geometry()

    def offset(self, vect):
        """
        Offsets the objects' geometry on the XY plane by a given vector.
        These are:

        * ``buffered_paths``
        * ``flash_geometry``
        * ``solid_geometry``
        * ``regions``

        NOTE:
        Does not modify the data used to create these elements. If these
        are recreated, the scaling will be lost. This behavior was modified
        because of the complexity reached in this class.

        :param vect: (x, y) offset vector.
        :type vect: tuple
        :return: None
        """
        self.app.log.debug("ParseGerber.Gerber.offset()")

        try:
            dx, dy = vect
        except TypeError:
            self.app.inform.emit('[ERROR_NOTCL] %s' %
                                 _("An (x,y) pair of values are needed. "
                                   "Probable you entered only one value in the Offset field."))
            return

        if dx == 0 and dy == 0:
            return

        # variables to display the percentage of work done
        if isinstance(self.solid_geometry, (MultiPolygon, MultiLineString)):
            self.geo_len = len(self.solid_geometry.geoms)
        elif isinstance(self.solid_geometry, list):
            self.geo_len = len(self.solid_geometry)
        elif isinstance(self.solid_geometry, Polygon):
            self.geo_len = 1
        else:
            self.geo_len = 0

        self.old_disp_number = 0
        self.el_count = 0

        def offset_geom(obj):
            if type(obj) is list:
                new_obj = []
                for g in obj:
                    new_obj.append(offset_geom(g))
                return new_obj
            else:
                try:
                    self.el_count += 1
                    disp_number = int(np.interp(self.el_count, [0, self.geo_len], [0, 99]))
                    if self.old_disp_number < disp_number <= 100:
                        self.app.proc_container.update_view_text(' %d%%' % disp_number)
                        self.old_disp_number = disp_number

                    return affinity.translate(obj, xoff=dx, yoff=dy)
                except AttributeError:
                    return obj

        # ## Solid geometry
        self.solid_geometry = offset_geom(self.solid_geometry)
        self.follow_geometry = offset_geom(self.follow_geometry)

        # we need to offset the geometry stored in the Gerber apertures, too
        try:
            for apid in self.tools:
                if 'geometry' in self.tools[apid]:
                    for geo_el in self.tools[apid]['geometry']:
                        if 'solid' in geo_el:
                            geo_el['solid'] = offset_geom(geo_el['solid'])
                        if 'follow' in geo_el:
                            geo_el['follow'] = offset_geom(geo_el['follow'])
                        if 'clear' in geo_el:
                            geo_el['clear'] = offset_geom(geo_el['clear'])

        except Exception as e:
            self.app.log.error('ParseGerber.Gerber.offset() Exception --> %s' % str(e))
            return 'fail'

        self.app.inform.emit('[success] %s' % _("Done."))
        self.app.proc_container.new_text = ''

    def mirror(self, axis, point):
        """
        Mirrors the object around a specified axis passing through
        the given point. What is affected:

        * ``buffered_paths``
        * ``flash_geometry``
        * ``solid_geometry``
        * ``regions``

        NOTE:
        Does not modify the data used to create these elements. If these
        are recreated, the scaling will be lost. This behavior was modified
        because of the complexity reached in this class.

        :param axis: "X" or "Y" indicates around which axis to mirror.
        :type axis: str
        :param point: [x, y] point belonging to the mirror axis.
        :type point: list
        :return: None
        """
        self.app.log.debug("parseGerber.Gerber.mirror()")

        px, py = point
        xscale, yscale = {"X": (1.0, -1.0), "Y": (-1.0, 1.0)}[axis]

        # variables to display the percentage of work done
        self.geo_len = 0
        try:
            self.geo_len = len(self.solid_geometry)
        except TypeError:
            self.geo_len = 1

        self.old_disp_number = 0
        self.el_count = 0

        def mirror_geom(obj):
            if type(obj) is list:
                new_obj = []
                for g in obj:
                    new_obj.append(mirror_geom(g))
                return new_obj
            else:
                try:
                    self.el_count += 1
                    disp_number = int(np.interp(self.el_count, [0, self.geo_len], [0, 99]))
                    if self.old_disp_number < disp_number <= 100:
                        self.app.proc_container.update_view_text(' %d%%' % disp_number)
                        self.old_disp_number = disp_number

                    return affinity.scale(obj, xscale, yscale, origin=(px, py))
                except AttributeError:
                    return obj

        self.solid_geometry = mirror_geom(self.solid_geometry)
        self.follow_geometry = mirror_geom(self.follow_geometry)

        # we need to mirror the geometry stored in the Gerber apertures, too
        try:
            for apid in self.tools:
                if 'geometry' in self.tools[apid]:
                    for geo_el in self.tools[apid]['geometry']:
                        if 'solid' in geo_el:
                            geo_el['solid'] = mirror_geom(geo_el['solid'])
                        if 'follow' in geo_el:
                            geo_el['follow'] = mirror_geom(geo_el['follow'])
                        if 'clear' in geo_el:
                            geo_el['clear'] = mirror_geom(geo_el['clear'])
        except Exception as e:
            self.app.log.error('ParseGerber.Gerber.mirror() Exception --> %s' % str(e))
            return 'fail'

        self.app.inform.emit('[success] %s' % _("Done."))
        self.app.proc_container.new_text = ''

    def skew(self, angle_x, angle_y, point):
        """
        Shear/Skew the geometries of an object by angles along x and y dimensions.

        Parameters
        ----------
        angle_x, angle_y : float, float
            The shear angle(s) for the x and y axes respectively. These can be
            specified in either degrees (default) or radians by setting
            use_radians=True.

        See shapely manual for more information:
        http://toblerity.org/shapely/manual.html#affine-transformations
        :param angle_x: the angle on X axis for skewing
        :param angle_y: the angle on Y axis for skewing
        :param point: reference point for skewing operation
        :return None
        """
        self.app.log.debug("parseGerber.Gerber.skew()")

        px, py = point

        if angle_x == 0 and angle_y == 0:
            return

        # variables to display the percentage of work done
        self.geo_len = 0
        try:
            self.geo_len = len(self.solid_geometry)
        except TypeError:
            self.geo_len = 1

        self.old_disp_number = 0
        self.el_count = 0

        def skew_geom(obj):
            if type(obj) is list:
                new_obj = []
                for g in obj:
                    new_obj.append(skew_geom(g))
                return new_obj
            else:
                try:
                    self.el_count += 1
                    disp_number = int(np.interp(self.el_count, [0, self.geo_len], [0, 100]))
                    if self.old_disp_number < disp_number <= 100:
                        self.app.proc_container.update_view_text(' %d%%' % disp_number)
                        self.old_disp_number = disp_number

                    return affinity.skew(obj, angle_x, angle_y, origin=(px, py))
                except AttributeError:
                    return obj

        self.solid_geometry = skew_geom(self.solid_geometry)
        self.follow_geometry = skew_geom(self.follow_geometry)

        # we need to skew the geometry stored in the Gerber apertures, too
        try:
            for apid in self.tools:
                if 'geometry' in self.tools[apid]:
                    for geo_el in self.tools[apid]['geometry']:
                        if 'solid' in geo_el:
                            geo_el['solid'] = skew_geom(geo_el['solid'])
                        if 'follow' in geo_el:
                            geo_el['follow'] = skew_geom(geo_el['follow'])
                        if 'clear' in geo_el:
                            geo_el['clear'] = skew_geom(geo_el['clear'])
        except Exception as e:
            self.app.log.error('ParseGerber.Gerber.skew() Exception --> %s' % str(e))
            return 'fail'

        self.app.inform.emit('[success] %s' % _("Done."))
        self.app.proc_container.new_text = ''

    def rotate(self, angle, point):
        """
        Rotate an object by a given angle around given coords (point)
        :param angle:
        :param point:
        :return:
        """
        self.app.log.debug("parseGerber.Gerber.rotate()")

        px, py = point

        if angle == 0:
            return

        # variables to display the percentage of work done
        self.geo_len = 0
        try:
            self.geo_len = len(self.solid_geometry)
        except TypeError:
            self.geo_len = 1

        self.old_disp_number = 0
        self.el_count = 0

        def rotate_geom(obj):
            if type(obj) is list:
                new_obj = []
                for g in obj:
                    new_obj.append(rotate_geom(g))
                return new_obj
            else:
                try:
                    self.el_count += 1
                    disp_number = int(np.interp(self.el_count, [0, self.geo_len], [0, 100]))
                    if self.old_disp_number < disp_number <= 100:
                        self.app.proc_container.update_view_text(' %d%%' % disp_number)
                        self.old_disp_number = disp_number

                    return affinity.rotate(obj, angle, origin=(px, py))
                except AttributeError:
                    return obj

        self.solid_geometry = rotate_geom(self.solid_geometry)
        self.follow_geometry = rotate_geom(self.follow_geometry)

        # we need to rotate the geometry stored in the Gerber apertures, too
        try:
            for apid in self.tools:
                if 'geometry' in self.tools[apid]:
                    for geo_el in self.tools[apid]['geometry']:
                        if 'solid' in geo_el:
                            geo_el['solid'] = rotate_geom(geo_el['solid'])
                        if 'follow' in geo_el:
                            geo_el['follow'] = rotate_geom(geo_el['follow'])
                        if 'clear' in geo_el:
                            geo_el['clear'] = rotate_geom(geo_el['clear'])
        except Exception as e:
            self.app.log.error('ParseGerber.Gerber.rotate() Exception --> %s' % str(e))
            return 'fail'
        self.app.inform.emit('[success] %s' % _("Done."))
        self.app.proc_container.new_text = ''

    def buffer(self, distance, join=2, factor=None, only_exterior=False):
        """

        :param distance:        If 'factor' is True then distance is the factor
        :param join:            The type of joining used by the Shapely buffer method. Can be: round, square and bevel
        :param factor:          True or False (None)
        :param only_exterior:   Bool. If True, the LineStrings are buffered only on the outside
        :return:                None
        """
        self.app.log.debug("parseGerber.Gerber.buffer()")

        if distance == 0:
            return

        # variables to display the percentage of work done
        self.geo_len = 0
        try:
            if isinstance(self.solid_geometry, (MultiPolygon, MultiLineString)):
                self.geo_len = len(self.solid_geometry.geoms)
            if isinstance(self.solid_geometry, list):
                self.geo_len = len(self.solid_geometry)
        except (TypeError, ValueError, RuntimeError):
            self.geo_len = 1

        self.old_disp_number = 0
        self.el_count = 0

        if factor is None:
            def buffer_geom(obj):
                new_obj = []
                try:
                    work_geo = obj.geoms if isinstance(obj, (MultiPolygon, MultiLineString)) else obj
                    for g in work_geo:
                        new_obj.append(buffer_geom(g))
                except TypeError:
                    try:
                        new_obj = obj.buffer(distance, resolution=self.steps_per_circle, join_style=join)
                        if isinstance(obj, (LinearRing, LineString)) and only_exterior is True:
                            new_obj = new_obj.exterior
                    except AttributeError:
                        new_obj = obj

                return new_obj

            self.solid_geometry = flatten_shapely_geometry(buffer_geom(self.solid_geometry))

            # we need to buffer the geometry stored in the Gerber apertures, too
            try:
                for apid in self.tools:
                    new_geometry = []
                    if 'geometry' in self.tools[apid]:
                        for geo_el in self.tools[apid]['geometry']:
                            new_geo_el = {}
                            if 'solid' in geo_el:
                                new_geo_el['solid'] = buffer_geom(geo_el['solid'])
                            if 'follow' in geo_el:
                                new_geo_el['follow'] = geo_el['follow']
                            if 'clear' in geo_el:
                                new_geo_el['clear'] = buffer_geom(geo_el['clear'])
                            new_geometry.append(new_geo_el)

                    self.tools[apid]['geometry'] = deepcopy(new_geometry)

                    try:
                        if str(self.tools[apid]['type']) == 'R' or str(self.tools[apid]['type']) == 'O':
                            self.tools[apid]['width'] += (distance * 2)
                            self.tools[apid]['height'] += (distance * 2)
                        elif str(self.tools[apid]['type']) == 'P':
                            self.tools[apid]['diam'] += (distance * 2)
                            self.tools[apid]['nVertices'] += (distance * 2)
                    except KeyError:
                        pass

                    try:
                        if self.tools[apid]['size'] is not None:
                            self.tools[apid]['size'] = float(self.tools[apid]['size'] + (distance * 2))
                    except KeyError:
                        pass
            except Exception as e:
                self.app.log.error('ParseGerber.Gerber.buffer() Exception --> %s' % str(e))
                return 'fail'
        else:
            try:
                for apid in self.tools:
                    try:
                        if str(self.tools[apid]['type']) == 'R' or str(self.tools[apid]['type']) == 'O':
                            self.tools[apid]['width'] *= distance
                            self.tools[apid]['height'] *= distance
                        elif str(self.tools[apid]['type']) == 'P':
                            self.tools[apid]['diam'] *= distance
                            self.tools[apid]['nVertices'] *= distance
                    except KeyError:
                        pass

                    try:
                        if self.tools[apid]['size'] is not None:
                            self.tools[apid]['size'] = float(self.tools[apid]['size']) * distance
                    except KeyError:
                        pass

                    new_geometry = []
                    if 'geometry' in self.tools[apid]:
                        for geo_el in self.tools[apid]['geometry']:
                            new_geo_el = {}
                            if 'follow' in geo_el:
                                new_geo_el['follow'] = geo_el['follow']
                                size = float(self.tools[apid]['size'])
                                if isinstance(new_geo_el['follow'], Point):
                                    if str(self.tools[apid]['type']) == 'C':
                                        new_geo_el['solid'] = geo_el['follow'].buffer(
                                            size / 1.9999,
                                            resolution=int(self.steps_per_circle)
                                        )
                                    elif str(self.tools[apid]['type']) == 'R':
                                        width = self.tools[apid]['width']
                                        height = self.tools[apid]['height']
                                        minx = new_geo_el['follow'].x - width / 2
                                        maxx = new_geo_el['follow'].x + width / 2
                                        miny = new_geo_el['follow'].y - height / 2
                                        maxy = new_geo_el['follow'].y + height / 2

                                        geo_p = shply_box(minx, miny, maxx, maxy)
                                        new_geo_el['solid'] = geo_p
                                    else:
                                        self.app.log.debug(
                                            "appParsers.ParseGerber.Gerber.buffer() --> ap type not supported")
                                else:
                                    new_geo_el['solid'] = geo_el['follow'].buffer(
                                        size/1.9999,
                                        resolution=int(self.steps_per_circle)
                                    )
                            if 'clear' in geo_el:
                                new_geo_el['clear'] = geo_el['clear']
                            new_geometry.append(new_geo_el)

                    self.tools[apid]['geometry'] = deepcopy(new_geometry)
            except Exception as e:
                self.app.log.error('ParseGerber.Gerber.buffer() Exception --> %s' % str(e))
                return 'fail'

            # make the new solid_geometry
            new_solid_geo = []
            for apid in self.tools:
                if 'geometry' in self.tools[apid]:
                    new_solid_geo += [geo_el['solid'] for geo_el in self.tools[apid]['geometry']]

            self.solid_geometry = MultiPolygon(new_solid_geo)
            self.solid_geometry = self.solid_geometry.buffer(0.000001)
            self.solid_geometry = self.solid_geometry.buffer(-0.000001)

        self.app.inform.emit('[success] %s' % _("Gerber Buffer done."))
        self.app.proc_container.new_text = ''


def parse_gerber_number(strnumber, int_digits, frac_digits, zeros):
    """
    Parse a single number of Gerber coordinates.

    :param strnumber:       String containing a number in decimal digits
                            from a coordinate data block, possibly with a leading sign.
    :type strnumber:        str
    :param int_digits:      Number of digits used for the integer
                            part of the number
    :type frac_digits:      int
    :param frac_digits:     Number of digits used for the fractional
                            part of the number
    :type frac_digits:      int
    :param zeros:           If 'L', leading zeros are removed and trailing zeros are kept. Same situation for 'D' when
                            no zero suppression is done. If 'T', is in reverse.
    :type zeros:            str
    :return:                The number in floating point.
    :rtype:                 float
    """

    ret_val = None

    if zeros == 'L' or zeros == 'D':
        ret_val = int(strnumber) * (10 ** (-frac_digits))

    if zeros == 'T':
        int_val = int(strnumber)
        if int_val >= 0:
            ret_val = (int_val * (10 ** ((int_digits + frac_digits) - len(strnumber)))) * (10 ** (-frac_digits))
        else:
            # negative number therefore we have a '-' char in front of the strnumber
            ret_val = (int_val * (10 ** ((int_digits + frac_digits + 1) - len(strnumber)))) * (10 ** (-frac_digits))

        # if strnumber[0] == '-':
        #     int_val = strnumber[:(int_digits+1)]
        #     frac_val = strnumber[(int_digits+1):]
        # else:
        #     int_val = strnumber[:int_digits]
        #     frac_val = strnumber[(int_digits):]
        # ret_val = '%s.%s' % (int_val, frac_val)
        # ret_val = float(ret_val)

    return ret_val
