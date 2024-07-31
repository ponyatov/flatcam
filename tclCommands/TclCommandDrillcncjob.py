from tclCommands.TclCommand import TclCommandSignaled

import collections
import math

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class TclCommandDrillcncjob(TclCommandSignaled):
    """
    Tcl shell command to Generates a Drill CNC Job from a Excellon Object.
    """

    # array of all command aliases, to be able use  old names for backward compatibility (add_poly, add_polygon)
    aliases = ['drillcncjob']

    description = '%s %s' % ("--", "Generates a Drill CNC Job object from a Excellon Object.")

    # dictionary of types from Tcl command, needs to be ordered
    arg_names = collections.OrderedDict([
        ('name', str)
    ])

    # dictionary of types from Tcl command, needs to be ordered , this  is  for options  like -optionname value
    option_types = collections.OrderedDict([
        ('drilled_dias', str),
        ('drillz', float),
        ('dpp', float),
        ('travelz', float),
        ('feedrate_z', float),
        ('feedrate_rapid', float),
        ('spindlespeed', int),
        ('toolchangez', float),
        ('toolchangexy', str),
        ('startz', float),
        ('endz', float),
        ('endxy', str),
        ('dwelltime', float),
        ('las_power', float),
        ('las_min_pwr', float),
        ('pp', str),
        ('opt_type', str),
        ('diatol', float),
        ('muted', str),
        ('outname', str)
    ])

    # array of mandatory options for current Tcl command: required = {'name','outname'}
    required = ['name']

    # structured help for current command, args needs to be ordered
    help = {
        'main': "Generates a Drill CNC Job from a Excellon Object.",
        'args': collections.OrderedDict([
            ('name', 'Name of the source object.'),
            ('drilled_dias',
             'Comma separated tool diameters of the drills to be drilled (example: 0.6,1.0 or 3.125). '
             'WARNING: No space allowed. Can also take the value "all" which will drill the holes for all tools.'),
            ('drillz', 'Drill depth into material (example: -2.0).'),
            ('dpp', 'Progressive drilling into material with a specified step (example: 0.7). Positive value.'),
            ('travelz', 'Travel distance above material (example: 2.0).'),
            ('feedrate_z', 'Drilling feed rate. It is the speed on the Z axis.'),
            ('feedrate_rapid', 'Rapid drilling feed rate.'),
            ('spindlespeed', 'Speed of the spindle in rpm (example: 4000).'),
            ('toolchangez', 'Z distance for toolchange (example: 30.0).\n'
                            'If used in the command then a toolchange event will be included in gcode'),
            ('toolchangexy', 'The X,Y coordinates at Toolchange event in format (x, y) (example: (30.0, 15.2) or '
                             'without parenthesis like: 0.3,1.0). WARNING: no spaces allowed in the value.'),
            ('startz', 'The Z coordinate at job start (example: 30.0).'),
            ('endz', 'The Z coordinate at job end (example: 30.0).'),
            ('endxy', 'The X,Y coordinates at job end in format (x, y) (example: (2.0, 1.2) or without parenthesis'
                      'like: 0.3,1.0). WARNING: no spaces allowed in the value.'),
            ('dwelltime', 'Time to pause to allow the spindle to reach the full speed.\n'
                          'If it is not used in command then it will not be included'),
            ('las_power', 'Used with "laser" preprocessors. Set the laser power when cutting'),
            ('las_min_pwr', 'Used with "laser" preprocessors. Set the laser power when not cutting, travelling'),
            ('pp', 'This is the Excellon preprocessor name: case_sensitive, no_quotes'),
            ('opt_type', 'Name of move optimization type. B by default for Basic OR-Tools, M for Metaheuristic OR-Tools'
                         'T from Travelling Salesman Algorithm. B and M works only for 64bit application flavor and '
                         'T works only for 32bit application flavor'),
            ('diatol', 'Tolerance. Percentange (0.0 ... 100.0) within which dias in drilled_dias will be judged to be '
                       'the same as the ones in the tools from the Excellon object. E.g: if in drill_dias we have a '
                       'diameter with value 1.0, in the Excellon we have a tool with dia = 1.05 and we set a tolerance '
                       'diatol = 5.0 then the drills with the dia = (0.95 ... 1.05) '
                       'in Excellon will be processed. Float number.'),
            ('muted', 'It will not put errors in the Shell or status bar. Can be True (1) or False (0).'),
            ('outname', 'Name of the resulting Geometry object.')
        ]),
        'examples': ['drillcncjob test.TXT -drillz -1.5 -travelz 14 -feedrate_z 222 -feedrate_rapid 456 '
                     '-spindlespeed 777 -toolchangez 33 -endz 22 -pp Marlin\n'
                     'Usage of -feedrate_rapid matter only when the preprocessor is using it, like -Marlin-.\n',
                     'drillcncjob test.DRL -drillz -1.7 -dpp 0.5 -travelz 2 -feedrate_z 800 -endxy 3,3\n',
                     'drillcncjob test.DRL -drilled_dias "all" -drillz -1.7 -dpp 0.5 -travelz 2 -feedrate_z 800 '
                     '-endxy 3,3'
                     ]
    }

    def execute(self, args, unnamed_args):
        """
        execute current TCL shell command

        :param args: array of known named arguments and options
        :param unnamed_args: array of other values which were passed into command
            without -somename and  we do not have them in known arg_names
        :return: None or exception
        """

        name = args['name']

        obj = self.app.collection.get_by_name(name)

        if 'outname' not in args:
            args['outname'] = name + "_cnc"

        if 'muted' in args:
            try:
                par = args['muted'].capitalize()
            except AttributeError:
                par = args['muted']
            muted = bool(eval(par))
        else:
            muted = False

        if obj is None:
            if muted is False:
                self.raise_tcl_error("Object not found: %s" % name)
            self.app.log.error("Object not found: %s" % name)
            return "fail"

        if obj.kind != 'excellon':
            if muted is False:
                self.raise_tcl_error('Expected ExcellonObject, got %s %s.' % (name, type(obj)))
            self.app.log.error('Expected ExcellonObject, got %s %s.' % (name, type(obj)))
            return "fail"

        xmin = obj.obj_options['xmin']
        ymin = obj.obj_options['ymin']
        xmax = obj.obj_options['xmax']
        ymax = obj.obj_options['ymax']

        def job_init(cnc_job_obj, app_obj):
            # tools = args["tools"] if "tools" in args else 'all'
            use_tools = []

            # drilled tools diameters
            try:
                if 'drilled_dias' in args and args['drilled_dias'] != 'all':
                    diameters = [x.strip() for x in args['drilled_dias'].split(",") if x != '']
                    nr_diameters = len(diameters)

                    req_tools = set()
                    for tool in obj.tools:
                        obj_dia_form = float('%.*f' % (obj.decimals, float(obj.tools[tool]["tooldia"])))
                        for req_dia in diameters:
                            req_dia_form = float('%.*f' % (obj.decimals, float(req_dia)))

                            if 'diatol' in args:
                                tolerance = args['diatol'] / 100

                                tolerance = 0.0 if tolerance < 0.0 else tolerance
                                tolerance = 1.0 if tolerance > 1.0 else tolerance
                                if math.isclose(obj_dia_form, req_dia_form, rel_tol=tolerance):
                                    req_tools.add(str(tool))
                                    nr_diameters -= 1
                                    use_tools.append(tool)
                            else:
                                if obj_dia_form == req_dia_form:
                                    req_tools.add(str(tool))
                                    nr_diameters -= 1
                                    use_tools.append(tool)

                    if nr_diameters > 0:
                        if muted is False:
                            self.raise_tcl_error("One or more tool diameters of the drills to be drilled passed to the "
                                                 "TclCommand are not actual tool diameters in the Excellon object.")
                        else:
                            app_obj.log.error("One or more tool diameters of the drills to be drilled passed to the "\
                                              "TclCommand are not actual tool diameters in the Excellon object.")
                            return "fail"

                    # make a string of diameters separated by comma; this is what tcl_gcode_from_excellon_by_tool() is
                    # expecting as tools parameter
                    tools = ','.join(req_tools)

                    # no longer needed
                    # del args['drilled_dias']
                    args.pop('drilled_dias', None)
                    args.pop('diatol', None)

                    # Split and put back. We are passing the whole dictionary later.
                    # args['milled_dias'] = [x.strip() for x in args['tools'].split(",")]
                else:
                    tools = 'all'
            except Exception as e:
                tools = 'all'

                if muted is False:
                    self.raise_tcl_error("Bad tools: %s" % str(e))

                self.app.log.error("Bad tools: %s" % str(e))
                return "fail"

            # populate the information's list for used tools
            if tools == 'all':
                sort = []
                for k, v in list(obj.tools.items()):
                    sort.append((k, v.get('tooldia')))
                sorted_tools = sorted(sort, key=lambda t1: t1[1])
                use_tools = [i[0] for i in sorted_tools]

            drillz = args["drillz"] if "drillz" in args and args["drillz"] is not None else \
                obj.obj_options["tools_drill_cutz"]

            toolchange = self.app.options["tools_drill_toolchange"]
            if "toolchangez" in args:
                toolchange = True
                if args["toolchangez"] is not None:
                    toolchangez = args["toolchangez"]
                else:
                    toolchangez = obj.obj_options["tools_drill_toolchangez"]
            else:
                toolchangez = float(self.app.options["tools_drill_toolchangez"])

            if "toolchangexy" in args and args["toolchangexy"]:
                toolchange = True
                xy_toolchange = args["toolchangexy"]
            else:
                if self.app.options["tools_drill_toolchangexy"]:
                    xy_toolchange = str(self.app.options["tools_drill_toolchangexy"])
                else:
                    xy_toolchange = '0, 0'
            if len(eval(xy_toolchange)) != 2:
                self.raise_tcl_error("The entered value for 'toolchangexy' needs to have the format x,y or "
                                     "in format (x, y) - no spaces allowed. But always two comma separated values.")
                self.app.log.error("The entered value for 'toolchangexy' needs to have the format x,y or "
                                   "in format (x, y) - no spaces allowed. But always two comma separated values.")
                return "fail"

            endz = args["endz"] if "endz" in args and args["endz"] is not None else \
                self.app.options["tools_drill_endz"]

            if "endxy" in args and args["endxy"]:
                xy_end = args["endxy"]
            else:
                if self.app.options["tools_drill_endxy"]:
                    xy_end = str(self.app.options["tools_drill_endxy"])
                else:
                    xy_end = '0, 0'

            if len(eval(xy_end)) != 2:
                self.raise_tcl_error("The entered value for 'xy_end' needs to have the format x,y or "
                                     "in format (x, y) - no spaces allowed. But always two comma separated values.")
                self.app.log.error("The entered value for 'xy_end' needs to have the format x,y or "
                                   "in format (x, y) - no spaces allowed. But always two comma separated values.")
                return "fail"

            # Path optimization
            opt_type = args["opt_type"] if "opt_type" in args and args["opt_type"] else 'R'

            # ##########################################################################################
            # ################# Set parameters #########################################################
            # ##########################################################################################
            cnc_job_obj.obj_options['type'] = 'Excellon'
            cnc_job_obj.multigeo = True
            cnc_job_obj.multitool = True
            cnc_job_obj.used_tools = use_tools

            # preprocessor
            pp_excellon_name = args["pp"] if "pp" in args and args["pp"] else self.app.options["tools_drill_ppname_e"]
            cnc_job_obj.pp_excellon_name = pp_excellon_name
            cnc_job_obj.obj_options['ppname_e'] = pp_excellon_name

            # multidepth
            if 'dpp' in args:
                cnc_job_obj.multidepth = True
                if args['dpp'] is not None:
                    cnc_job_obj.z_depthpercut = abs(float(args['dpp']))
                else:
                    cnc_job_obj.z_depthpercut = abs(float(obj.obj_options["dpp"]))
            else:
                cnc_job_obj.multidepth = self.app.options["tools_drill_multidepth"]
                cnc_job_obj.z_depthpercut = self.app.options["tools_drill_depthperpass"]
            # travel Z
            cnc_job_obj.z_move = float(args["travelz"]) if "travelz" in args and args["travelz"] else \
                self.app.options["tools_drill_travelz"]
            # Feedrate
            cnc_job_obj.feedrate = float(args["feedrate_z"]) if "feedrate_z" in args and args["feedrate_z"] else \
                self.app.options["tools_drill_feedrate_z"]
            cnc_job_obj.z_feedrate = float(args["feedrate_z"]) if "feedrate_z" in args and args["feedrate_z"] else \
                self.app.options["tools_drill_feedrate_z"]
            cnc_job_obj.feedrate_rapid = float(args["feedrate_rapid"]) \
                if "feedrate_rapid" in args and args["feedrate_rapid"] else \
                self.app.options["tools_drill_feedrate_rapid"]

            # SpindleSpped / Laser Power
            if 'laser' not in pp_excellon_name:
                cnc_job_obj.spindlespeed = float(args["spindlespeed"]) if "spindlespeed" in args else None
            else:
                cnc_job_obj.spindlespeed = float(args["las_power"]) if "las_power" in args else 0.0

            # laser minimum power
            cnc_job_obj.laser_min_power = float(args["las_min_pwr"]) if "las_min_pwr" in args else 0.0

            # spindle direction
            cnc_job_obj.spindledir = self.app.options["tools_drill_spindledir"]
            # dwell and dwelltime
            if 'dwelltime' in args:
                cnc_job_obj.dwell = True
                if args['dwelltime'] is not None:
                    cnc_job_obj.dwelltime = float(args['dwelltime'])
                else:
                    cnc_job_obj.dwelltime = float(self.app.options["tools_drill_dwelltime"])
            else:
                cnc_job_obj.dwell = self.app.options["tools_drill_dwell"]
                cnc_job_obj.dwelltime = self.app.options["tools_drill_dwelltime"]

            cnc_job_obj.coords_decimals = int(self.app.options["cncjob_coords_decimals"])
            cnc_job_obj.fr_decimals = int(self.app.options["cncjob_fr_decimals"])

            cnc_job_obj.obj_options['xmin'] = xmin
            cnc_job_obj.obj_options['ymin'] = ymin
            cnc_job_obj.obj_options['xmax'] = xmax
            cnc_job_obj.obj_options['ymax'] = ymax

            # Cut Z
            cnc_job_obj.z_cut = float(drillz)
            # toolchange
            cnc_job_obj.toolchange = toolchange
            # toolchange X-Y location
            cnc_job_obj.xy_toolchange = xy_toolchange
            # toolchange Z location
            cnc_job_obj.z_toolchange = float(toolchangez)
            # start Z
            if "startz" in args and args["startz"] is not None:
                cnc_job_obj.startz = float(args["startz"])
            else:
                if self.app.options["tools_drill_startz"]:
                    cnc_job_obj.startz = self.app.options["tools_drill_startz"]
                else:
                    cnc_job_obj.startz = self.app.options["tools_drill_travelz"]
            # end Z
            cnc_job_obj.z_end = float(endz)
            # end X-Y location
            cnc_job_obj.xy_end = eval(str(xy_end))
            # Excellon optimization
            cnc_job_obj.excellon_optimization_type = opt_type

            ret_val = cnc_job_obj.tcl_gcode_from_excellon_by_tool(obj, tools, is_first=True)
            if ret_val == 'fail':
                return 'fail'

            cnc_job_obj.source_file = ret_val
            cnc_job_obj.gc_start = ret_val[1]

            total_gcode_parsed = []
            if cnc_job_obj.toolchange is True:
                if tools == "all":
                    processed_tools = list(cnc_job_obj.tools.keys())
                else:
                    processed_tools = use_tools

                # from Excellon attribute self.tools
                for t_item in processed_tools:
                    cnc_job_obj.tools[t_item]['data']['tools_drill_offset'] = \
                        float(cnc_job_obj.tools[t_item]['offset_z']) + float(drillz)
                    cnc_job_obj.tools[t_item]['data']['tools_drill_ppname_e'] = cnc_job_obj.obj_options['ppname_e']

                    used_tooldia = obj.tools[t_item]['tooldia']
                    cnc_job_obj.tools[t_item]['tooldia'] = used_tooldia
                    tool_gcode = cnc_job_obj.tools[t_item]['gcode']
                    first_drill_point = cnc_job_obj.tools[t_item]['last_point']
                    gcode_parsed = cnc_job_obj.excellon_tool_gcode_parse(used_tooldia, gcode=tool_gcode,
                                                                         start_pt=first_drill_point)
                    total_gcode_parsed += gcode_parsed
                    cnc_job_obj.tools[t_item]['gcode_parsed'] = gcode_parsed
            else:
                if tools == "all":
                    first_tool = 1
                else:
                    first_tool = use_tools[0]

                cnc_job_obj.tools[first_tool]['data']['tools_drill_offset'] = \
                    float(cnc_job_obj.tools[first_tool]['offset_z']) + float(drillz)
                cnc_job_obj.tools[first_tool]['data']['tools_drill_ppname_e'] = cnc_job_obj.obj_options['ppname_e']

                used_tooldia = obj.tools[first_tool]['tooldia']
                cnc_job_obj.tools[first_tool]['tooldia'] = used_tooldia
                tool_gcode = cnc_job_obj.tools[first_tool]['gcode']
                first_drill_point = cnc_job_obj.tools[first_tool]['last_point']
                gcode_parsed = cnc_job_obj.excellon_tool_gcode_parse(used_tooldia, gcode=tool_gcode,
                                                                     start_pt=first_drill_point)
                total_gcode_parsed += gcode_parsed
                cnc_job_obj.tools[first_tool]['gcode_parsed'] = gcode_parsed

            cnc_job_obj.gcode_parsed = total_gcode_parsed
            # cnc_job_obj.gcode_parse()
            cnc_job_obj.create_geometry()

        self.app.app_obj.new_object("cncjob", args['outname'], job_init, plot=False)
