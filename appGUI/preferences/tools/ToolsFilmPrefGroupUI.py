
from PyQt6 import QtGui

from appGUI.GUIElements import RadioSet, FCDoubleSpinner, FCCheckBox, FCComboBox, FCColorEntry, FCLabel, FCSpinner, \
    GLay, FCComboBox2, FCFrame
from appGUI.preferences.OptionsGroupUI import OptionsGroupUI

import gettext
import appTranslation as fcTranslate
import builtins

fcTranslate.apply_language('strings')
if '_' not in builtins.__dict__:
    _ = gettext.gettext


class ToolsFilmPrefGroupUI(OptionsGroupUI):
    def __init__(self, app, parent=None):
        # OptionsGroupUI.__init__(self, "Cutout Plugin", parent=parent)
        super(ToolsFilmPrefGroupUI, self).__init__(self, parent=parent)

        self.setTitle(str(_("Film Plugin")))
        self.decimals = app.decimals
        self.options = app.options

        # #############################################################################################################
        # Adjustments Frame
        # #############################################################################################################
        self.film_adj_label = FCLabel('%s' % _("Adjustments"), color='brown', bold=True)
        self.film_adj_label.setToolTip(
            _("Compensate print distortions.")
        )

        self.layout.addWidget(self.film_adj_label)

        adj_frame = FCFrame()
        self.layout.addWidget(adj_frame)

        adj_grid = GLay(v_spacing=5, h_spacing=3)
        adj_frame.setLayout(adj_grid)

        # Scale Geometry
        self.film_scale_cb = FCCheckBox('%s' % _("Scale"))
        self.film_scale_cb.setToolTip(
            _("A value greater than 1 will compact the film\n"
              "while a value less than 1 will jolt it.")
        )
        adj_grid.addWidget(self.film_scale_cb, 2, 0, 1, 2)

        # SCALE FRAME
        scale_frame = FCFrame()
        adj_grid.addWidget(scale_frame, 4, 0, 1, 2)

        grid_scale = GLay(v_spacing=5, h_spacing=3)
        scale_frame.setLayout(grid_scale)

        # Scale Type
        self.film_scale_type_lbl = FCLabel('%s:' % _("Type"))
        self.film_scale_type_lbl.setToolTip(
            _("'Length' -> scale by a length value\n"
              "'Factor' -> scale by a ratio")
        )
        self.film_scale_type_combo = FCComboBox2()
        self.film_scale_type_combo.addItems([_("Length"), _("Factor")])

        grid_scale.addWidget(self.film_scale_type_lbl, 0, 0)
        grid_scale.addWidget(self.film_scale_type_combo, 0, 1)

        # Scale X factor
        self.film_scalex_label = FCLabel('%s:' % _("X val"))
        self.film_scalex_entry = FCDoubleSpinner()
        self.film_scalex_entry.set_range(-10000.0000, 10000.0000)
        self.film_scalex_entry.set_precision(self.decimals)
        self.film_scalex_entry.setSingleStep(0.01)

        grid_scale.addWidget(self.film_scalex_label, 2, 0)
        grid_scale.addWidget(self.film_scalex_entry, 2, 1)

        # Scale Y factor
        self.film_scaley_label = FCLabel('%s:' % _("Y val"))
        self.film_scaley_entry = FCDoubleSpinner()
        self.film_scaley_entry.set_range(-10000.0000, 10000.0000)
        self.film_scaley_entry.set_precision(self.decimals)
        self.film_scaley_entry.setSingleStep(0.01)

        grid_scale.addWidget(self.film_scaley_label, 4, 0)
        grid_scale.addWidget(self.film_scaley_entry, 4, 1)

        # Scale reference
        self.scale_ref_label = FCLabel('%s:' % _("Reference"))
        self.scale_ref_label.setToolTip(
            _("The reference point to be used as origin for the adjustment.")
        )

        self.film_scale_ref_combo = FCComboBox2()
        self.film_scale_ref_combo.addItems(
            [_('Center'), _('Bottom Left'), _('Top Left'), _('Bottom Right'), _('Top right')])

        grid_scale.addWidget(self.scale_ref_label, 6, 0)
        grid_scale.addWidget(self.film_scale_ref_combo, 6, 1)

        # Skew Geometry
        self.film_skew_cb = FCCheckBox('%s' % _("Skew"))
        self.film_skew_cb.setToolTip(
            _("Positive values will skew to the right\n"
              "while negative values will skew to the left.")
        )
        adj_grid.addWidget(self.film_skew_cb, 8, 0, 1, 2)

        # SKEW FRAME
        skew_frame = FCFrame()
        adj_grid.addWidget(skew_frame, 10, 0, 1, 2)

        grid_skew = GLay(v_spacing=5, h_spacing=3)
        skew_frame.setLayout(grid_skew)

        self.film_skew_type_lbl = FCLabel('%s:' % _("Type"))
        self.film_skew_type_lbl.setToolTip(
            _("'Length' -> deform by a length value\n"
              "'Angle' -> deform by an angle\n"
              "'Factor' -> deform by a ratio between what should be and what is")
        )
        self.film_skew_type_combo = FCComboBox2()
        self.film_skew_type_combo.addItems([_("Length"), _("Angle"), _("Factor")])

        grid_skew.addWidget(self.film_skew_type_lbl, 0, 0)
        grid_skew.addWidget(self.film_skew_type_combo, 0, 1)

        self.film_skewx_label = FCLabel('%s:' % _("X val"))
        self.film_skewx_entry = FCDoubleSpinner()
        self.film_skewx_entry.set_range(-10000.0000, 10000.0000)
        self.film_skewx_entry.set_precision(self.decimals)
        self.film_skewx_entry.setSingleStep(0.01)

        grid_skew.addWidget(self.film_skewx_label, 2, 0)
        grid_skew.addWidget(self.film_skewx_entry, 2, 1)

        self.film_skewy_label = FCLabel('%s:' % _("Y val"))
        self.film_skewy_entry = FCDoubleSpinner()
        self.film_skewy_entry.set_range(-10000.0000, 10000.0000)
        self.film_skewy_entry.set_precision(self.decimals)
        self.film_skewy_entry.setSingleStep(0.01)

        grid_skew.addWidget(self.film_skewy_label, 4, 0)
        grid_skew.addWidget(self.film_skewy_entry, 4, 1)

        # Skew Reference
        self.skew_ref_label = FCLabel('%s:' % _("Reference"))
        self.skew_ref_label.setToolTip(
            _("The reference point to be used as origin for the adjustment.")
        )

        self.film_skew_ref_combo = FCComboBox2()
        self.film_skew_ref_combo.addItems(
            [_('Center'), _('Bottom Left')])

        grid_skew.addWidget(self.skew_ref_label, 6, 0)
        grid_skew.addWidget(self.film_skew_ref_combo, 6, 1)

        # Mirror Geometry
        self.film_mirror_cb = FCCheckBox('%s' % _("Mirror"))
        self.film_mirror_cb.setToolTip(
            _("Mirror the film geometry on the selected axis or on both.")
        )
        adj_grid.addWidget(self.film_mirror_cb, 12, 0, 1, 2)

        self.film_mirror_axis = RadioSet([{'label': _('X'), 'value': 'x'},
                                          {'label': _('Y'), 'value': 'y'},
                                          {'label': _('Both'), 'value': 'both'}],
                                         compact=True)
        self.film_mirror_axis_label = FCLabel('%s:' % _("Mirror Axis"))

        adj_grid.addWidget(self.film_mirror_axis_label, 14, 0)
        adj_grid.addWidget(self.film_mirror_axis, 14, 1)

        # separator_line3 = QtWidgets.QFrame()
        # separator_line3.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        # separator_line3.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        # self.layout.addWidget(separator_line3)

        # #############################################################################################################
        # Parameters Frame
        # #############################################################################################################
        self.film_label = FCLabel('%s' % _("Parameters"), color='blue', bold=True)
        self.film_label.setToolTip(
            _("Create a PCB film from a Gerber or Geometry object.\n"
              "The file is saved in SVG format.")
        )
        self.layout.addWidget(self.film_label)

        par_frame = FCFrame()
        self.layout.addWidget(par_frame)

        grid_par = GLay()
        par_frame.setLayout(grid_par)

        # Convex Shape
        # Surrounding convex box shape
        self.convex_box_label = FCLabel('%s:' % _("Convex Shape"))
        self.convex_box_label.setToolTip(
            _("Create a convex shape surrounding the entire PCB.\n"
              "If not checked the shape is rectangular.")
        )
        self.convex_box_cb = FCCheckBox()

        grid_par.addWidget(self.convex_box_label, 0, 0)
        grid_par.addWidget(self.convex_box_cb, 0, 1)

        # Rounded corners
        self.rounded_label = FCLabel('%s:' % _("Rounded"))
        self.rounded_label.setToolTip(
            _("Resulting geometry will have rounded corners.")
        )

        self.rounded_cb = FCCheckBox()

        grid_par.addWidget(self.rounded_label, 2, 0)
        grid_par.addWidget(self.rounded_cb, 2, 1)

        # Polarity
        self.film_type_radio = RadioSet([{'label': _('Positive'), 'value': 'pos'},
                                         {'label': _('Negative'), 'value': 'neg'}], compact=True)
        ftypelbl = FCLabel('%s:' % _('Polarity'))
        ftypelbl.setToolTip(
            _("Generate a Positive black film or a Negative film.")
        )
        grid_par.addWidget(ftypelbl, 4, 0)
        grid_par.addWidget(self.film_type_radio, 4, 1)

        # Film Color
        self.film_color_label = FCLabel('%s:' % _('Film Color'))
        self.film_color_label.setToolTip(
            _("Set the film color when positive film is selected.")
        )
        self.film_color_entry = FCColorEntry(icon=QtGui.QIcon(self.app.resource_location + '/set_colors64.png'))

        grid_par.addWidget(self.film_color_label, 6, 0)
        grid_par.addWidget(self.film_color_entry, 6, 1)

        # Film Border
        self.film_boundary_entry = FCDoubleSpinner()
        self.film_boundary_entry.set_precision(self.decimals)
        self.film_boundary_entry.set_range(0, 10000.0000)
        self.film_boundary_entry.setSingleStep(0.1)

        self.film_boundary_label = FCLabel('%s:' % _("Border"))
        self.film_boundary_label.setToolTip(
            _("Specify a border around the object.\n"
              "Only for negative film.\n"
              "It helps if we use as a Box Object the same \n"
              "object as in Film Object. It will create a thick\n"
              "black bar around the actual print allowing for a\n"
              "better delimitation of the outline features which are of\n"
              "white color like the rest and which may confound with the\n"
              "surroundings if not for this border.")
        )
        grid_par.addWidget(self.film_boundary_label, 8, 0)
        grid_par.addWidget(self.film_boundary_entry, 8, 1)

        # Scale Stroke
        self.film_scale_stroke_entry = FCDoubleSpinner()
        self.film_scale_stroke_entry.set_precision(self.decimals)
        self.film_scale_stroke_entry.set_range(0, 10000.0000)
        self.film_scale_stroke_entry.setSingleStep(0.1)

        self.film_scale_stroke_label = FCLabel('%s:' % _("Scale Stroke"))
        self.film_scale_stroke_label.setToolTip(
            _("Scale the line stroke thickness of each feature in the SVG file.\n"
              "It means that the line that envelope each SVG feature will be thicker or thinner,\n"
              "therefore the fine features may be more affected by this parameter.")
        )
        grid_par.addWidget(self.film_scale_stroke_label, 10, 0)
        grid_par.addWidget(self.film_scale_stroke_entry, 10, 1)

        self.file_type_radio = RadioSet([{'label': _('SVG'), 'value': 'svg'},
                                         {'label': _('PNG'), 'value': 'png'},
                                         {'label': _('PDF'), 'value': 'pdf'}
                                         ], compact=True)

        self.file_type_label = FCLabel('%s:' % _("Film Type"))
        self.file_type_label.setToolTip(
            _("The file type of the saved film. Can be:\n"
              "- 'SVG' -> open-source vectorial format\n"
              "- 'PNG' -> raster image\n"
              "- 'PDF' -> portable document format")
        )
        grid_par.addWidget(self.file_type_label, 12, 0)
        grid_par.addWidget(self.file_type_radio, 12, 1)

        # Page orientation
        self.orientation_label = FCLabel('%s:' % _("Page Orientation"))
        self.orientation_label.setToolTip(_("Can be:\n"
                                            "- Portrait\n"
                                            "- Landscape"))

        self.orientation_radio = RadioSet([{'label': _('Portrait'), 'value': 'p'},
                                           {'label': _('Landscape'), 'value': 'l'},
                                           ], compact=True)

        grid_par.addWidget(self.orientation_label, 14, 0)
        grid_par.addWidget(self.orientation_radio, 14, 1)

        # Page Size
        self.pagesize_label = FCLabel('%s:' % _("Page Size"))
        self.pagesize_label.setToolTip(_("A selection of standard ISO 216 page sizes."))

        self.pagesize_combo = FCComboBox()

        self.pagesize = {}
        self.pagesize.update(
            {
                'Bounds': None,
                'A0': (841, 1189),
                'A1': (594, 841),
                'A2': (420, 594),
                'A3': (297, 420),
                'A4': (210, 297),
                'A5': (148, 210),
                'A6': (105, 148),
                'A7': (74, 105),
                'A8': (52, 74),
                'A9': (37, 52),
                'A10': (26, 37),

                'B0': (1000, 1414),
                'B1': (707, 1000),
                'B2': (500, 707),
                'B3': (353, 500),
                'B4': (250, 353),
                'B5': (176, 250),
                'B6': (125, 176),
                'B7': (88, 125),
                'B8': (62, 88),
                'B9': (44, 62),
                'B10': (31, 44),

                'C0': (917, 1297),
                'C1': (648, 917),
                'C2': (458, 648),
                'C3': (324, 458),
                'C4': (229, 324),
                'C5': (162, 229),
                'C6': (114, 162),
                'C7': (81, 114),
                'C8': (57, 81),
                'C9': (40, 57),
                'C10': (28, 40),

                # American paper sizes
                'LETTER': (8.5, 11),
                'LEGAL': (8.5, 14),
                'ELEVENSEVENTEEN': (11, 17),

                # From https://en.wikipedia.org/wiki/Paper_size
                'JUNIOR_LEGAL': (5, 8),
                'HALF_LETTER': (5.5, 8),
                'GOV_LETTER': (8, 10.5),
                'GOV_LEGAL': (8.5, 13),
                'LEDGER': (17, 11),
            }
        )

        page_size_list = list(self.pagesize.keys())
        self.pagesize_combo.addItems(page_size_list)

        grid_par.addWidget(self.pagesize_label, 16, 0)
        grid_par.addWidget(self.pagesize_combo, 16, 1)

        # PNG DPI
        self.png_dpi_label = FCLabel('%s:' % "PNG DPI")
        self.png_dpi_label.setToolTip(
            _("Default value is 96 DPI. Change this value to scale the PNG file.")
        )
        self.png_dpi_spinner = FCSpinner()
        self.png_dpi_spinner.set_range(0, 100000)

        grid_par.addWidget(self.png_dpi_label, 18, 0)
        grid_par.addWidget(self.png_dpi_spinner, 18, 1)

        # self.layout.addStretch(1)

        GLay.set_common_column_size([adj_grid, grid_par, grid_skew, grid_scale], 0)

        # Film Tool
        self.film_color_entry.editingFinished.connect(self.on_film_color_entry)

    def on_film_color_entry(self):
        self.app.options['tools_film_color'] = self.film_color_entry.get_value()
