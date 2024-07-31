# ##########################################################
# FlatCAM Evo: 2D Post-processing for Manufacturing        #
# File Author: Marius Adrian Stanciu (c)                   #
# Date: 8/17/2019                                          #
# MIT Licence                                              #
# ##########################################################
import sys

from tclCommands.TclCommand import TclCommand

import collections


class TclCommandQuit(TclCommand):
    """
    Tcl shell command to quit the application from Tcl shell.

    example:

    """

    # List of all command aliases, to be able use old names for backward compatibility (add_poly, add_polygon)
    aliases = ['quit_app']

    description = '%s %s' % ("--", "Tcl shell command to quit the application from Tcl shell.")

    # Dictionary of types from Tcl command, needs to be ordered
    arg_names = collections.OrderedDict([

    ])

    # Dictionary of types from Tcl command, needs to be ordered , this  is  for options  like -optionname value
    option_types = collections.OrderedDict([

    ])

    # array of mandatory options for current Tcl command: required = {'name','outname'}
    required = []

    # structured help for current command, args needs to be ordered
    help = {
        'main': "Tcl shell command to quit the application from Tcl shell.",
        'args': collections.OrderedDict([

        ]),
        'examples': ['quit_app']
    }

    def execute(self, args, unnamed_args):
        """

        :param args:
        :param unnamed_args:
        :return:
        """

        try:
            self.app.quit_application(silent=True)
        except Exception:
            import os
            os._exit(0)
