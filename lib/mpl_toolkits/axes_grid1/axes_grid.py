from numbers import Number

import numpy as np

import matplotlib as mpl
from matplotlib import cbook
import matplotlib.ticker as ticker
from matplotlib.gridspec import SubplotSpec

from .axes_divider import Size, SubplotDivider, Divider
from .mpl_axes import Axes


def _tick_only(ax, bottom_on, left_on):
    bottom_off = not bottom_on
    left_off = not left_on
    ax.axis["bottom"].toggle(ticklabels=bottom_off, label=bottom_off)
    ax.axis["left"].toggle(ticklabels=left_off, label=left_off)


class CbarAxesBase:

    @cbook._rename_parameter("3.2", "locator", "ticks")
    def colorbar(self, mappable, *, ticks=None, **kwargs):

        if self.orientation in ["top", "bottom"]:
            orientation = "horizontal"
        else:
            orientation = "vertical"

        if mpl.rcParams["mpl_toolkits.legacy_colorbar"]:
            cbook.warn_deprecated(
                "3.2", message="Since %(since)s, mpl_toolkits's own colorbar "
                "implementation is deprecated; it will be removed "
                "%(removal)s.  Set the 'mpl_toolkits.legacy_colorbar' rcParam "
                "to False to use Matplotlib's default colorbar implementation "
                "and suppress this deprecation warning.")
            if ticks is None:
                ticks = ticker.MaxNLocator(5)  # For backcompat.
            from .colorbar import Colorbar
        else:
            from matplotlib.colorbar import Colorbar
        cb = Colorbar(
            self, mappable, orientation=orientation, ticks=ticks, **kwargs)
        self._config_axes()

        def on_changed(m):
            cb.set_cmap(m.get_cmap())
            cb.set_clim(m.get_clim())
            cb.update_bruteforce(m)

        self.cbid = mappable.callbacksSM.connect('changed', on_changed)
        mappable.colorbar = cb

        if mpl.rcParams["mpl_toolkits.legacy_colorbar"]:
            self.locator = cb.cbar_axis.get_major_locator()
        else:
            self.locator = cb.locator

        return cb

    def _config_axes(self):
        """Make an axes patch and outline."""
        ax = self
        ax.set_navigate(False)
        ax.axis[:].toggle(all=False)
        b = self._default_label_on
        ax.axis[self.orientation].toggle(all=b)

    def toggle_label(self, b):
        self._default_label_on = b
        axis = self.axis[self.orientation]
        axis.toggle(ticklabels=b, label=b)


class CbarAxes(CbarAxesBase, Axes):
    def __init__(self, *args, orientation, **kwargs):
        self.orientation = orientation
        self._default_label_on = True
        self.locator = None
        super().__init__(*args, **kwargs)

    def cla(self):
        super().cla()
        self._config_axes()


class Grid:
    """
    A class that creates a grid of Axes. In matplotlib, the axes
    location (and size) is specified in the normalized figure
    coordinates. This may not be ideal for images that needs to be
    displayed with a given aspect ratio.  For example, displaying
    images of a same size with some fixed padding between them cannot
    be easily done in matplotlib. AxesGrid is used in such case.
    """

    _defaultAxesClass = Axes

    def __init__(self, fig,
                 rect,
                 nrows_ncols,
                 ngrids=None,
                 direction="row",
                 axes_pad=0.02,
                 add_all=True,
                 share_all=False,
                 share_x=True,
                 share_y=True,
                 #aspect=True,
                 label_mode="L",
                 axes_class=None,
                 ):
        """
        Parameters
        ----------
        fig : `.Figure`
            The parent figure.
        rect : (float, float, float, float) or int
            The axes position, as a ``(left, bottom, width, height)`` tuple or
            as a three-digit subplot position code (e.g., "121").
        direction : {"row", "column"}, default: "row"
        axes_pad : float or (float, float), default: 0.02
            Padding or (horizontal padding, vertical padding) between axes, in
            inches.
        add_all : bool, default: True
        share_all : bool, default: False
        share_x : bool, default: True
        share_y : bool, default: True
        label_mode : {"L", "1", "all"}, default: "L"
            Determines which axes will get tick labels:

            - "L": All axes on the left column get vertical tick labels;
              all axes on the bottom row get horizontal tick labels.
            - "1": Only the bottom left axes is labelled.
            - "all": all axes are labelled.

        axes_class : subclass of `matplotlib.axes.Axes`, default: None
        """
        self._nrows, self._ncols = nrows_ncols

        if ngrids is None:
            ngrids = self._nrows * self._ncols
        else:
            if not 0 < ngrids <= self._nrows * self._ncols:
                raise Exception("")

        self.ngrids = ngrids

        self._init_axes_pad(axes_pad)

        cbook._check_in_list(["column", "row"], direction=direction)
        self._direction = direction

        if axes_class is None:
            axes_class = self._defaultAxesClass

        kw = dict(horizontal=[], vertical=[], aspect=False)
        if isinstance(rect, (str, Number, SubplotSpec)):
            self._divider = SubplotDivider(fig, rect, **kw)
        elif len(rect) == 3:
            self._divider = SubplotDivider(fig, *rect, **kw)
        elif len(rect) == 4:
            self._divider = Divider(fig, rect, **kw)
        else:
            raise Exception("")

        rect = self._divider.get_position()

        axes_array = np.full((self._nrows, self._ncols), None, dtype=object)
        for i in range(self.ngrids):
            col, row = self._get_col_row(i)
            if share_all:
                sharex = sharey = axes_array[0, 0]
            else:
                sharex = axes_array[0, col] if share_x else None
                sharey = axes_array[row, 0] if share_y else None
            axes_array[row, col] = axes_class(
                fig, rect, sharex=sharex, sharey=sharey)
        self.axes_all = axes_array.ravel().tolist()
        self.axes_column = axes_array.T.tolist()
        self.axes_row = axes_array.tolist()
        self.axes_llc = self.axes_column[0][-1]

        self._update_locators()

        if add_all:
            for ax in self.axes_all:
                fig.add_axes(ax)

        self.set_label_mode(label_mode)

    def _init_axes_pad(self, axes_pad):
        axes_pad = np.broadcast_to(axes_pad, 2)
        self._horiz_pad_size = Size.Fixed(axes_pad[0])
        self._vert_pad_size = Size.Fixed(axes_pad[1])

    def _update_locators(self):

        h = []
        h_ax_pos = []
        for _ in range(self._ncols):
            if h:
                h.append(self._horiz_pad_size)
            h_ax_pos.append(len(h))
            sz = Size.Scaled(1)
            h.append(sz)

        v = []
        v_ax_pos = []
        for _ in range(self._nrows):
            if v:
                v.append(self._vert_pad_size)
            v_ax_pos.append(len(v))
            sz = Size.Scaled(1)
            v.append(sz)

        for i in range(self.ngrids):
            col, row = self._get_col_row(i)
            locator = self._divider.new_locator(nx=h_ax_pos[col],
                                ny=v_ax_pos[self._nrows - 1 - row])
            self.axes_all[i].set_axes_locator(locator)

        self._divider.set_horizontal(h)
        self._divider.set_vertical(v)

    def _get_col_row(self, n):
        if self._direction == "column":
            col, row = divmod(n, self._nrows)
        else:
            row, col = divmod(n, self._ncols)

        return col, row

    # Good to propagate __len__ if we have __getitem__
    def __len__(self):
        return len(self.axes_all)

    def __getitem__(self, i):
        return self.axes_all[i]

    def get_geometry(self):
        """
        Return the number of rows and columns of the grid as (nrows, ncols).
        """
        return self._nrows, self._ncols

    def set_axes_pad(self, axes_pad):
        """
        Set the padding between the axes.

        Parameters
        ----------
        axes_pad : (float, float)
            The padding (horizontal pad, vertical pad) in inches.
        """
        # Differs from _init_axes_pad by 1) not broacasting, 2) modifying the
        # Size.Fixed objects in-place.
        self._horiz_pad_size.fixed_size = axes_pad[0]
        self._vert_pad_size.fixed_size = axes_pad[1]

    def get_axes_pad(self):
        """
        Return the axes padding.

        Returns
        -------
        hpad, vpad
            Padding (horizontal pad, vertical pad) in inches.
        """
        return (self._horiz_pad_size.fixed_size,
                self._vert_pad_size.fixed_size)

    def set_aspect(self, aspect):
        """Set the aspect of the SubplotDivider."""
        self._divider.set_aspect(aspect)

    def get_aspect(self):
        """Return the aspect of the SubplotDivider."""
        return self._divider.get_aspect()

    def set_label_mode(self, mode):
        """
        Define which axes have tick labels.

        Parameters
        ----------
        mode : {"L", "1", "all"}
            The label mode:

            - "L": All axes on the left column get vertical tick labels;
              all axes on the bottom row get horizontal tick labels.
            - "1": Only the bottom left axes is labelled.
            - "all": all axes are labelled.
        """
        if mode == "all":
            for ax in self.axes_all:
                _tick_only(ax, False, False)
        elif mode == "L":
            # left-most axes
            for ax in self.axes_column[0][:-1]:
                _tick_only(ax, bottom_on=True, left_on=False)
            # lower-left axes
            ax = self.axes_column[0][-1]
            _tick_only(ax, bottom_on=False, left_on=False)

            for col in self.axes_column[1:]:
                # axes with no labels
                for ax in col[:-1]:
                    _tick_only(ax, bottom_on=True, left_on=True)

                # bottom
                ax = col[-1]
                _tick_only(ax, bottom_on=False, left_on=True)

        elif mode == "1":
            for ax in self.axes_all:
                _tick_only(ax, bottom_on=True, left_on=True)

            ax = self.axes_llc
            _tick_only(ax, bottom_on=False, left_on=False)

    def get_divider(self):
        return self._divider

    def set_axes_locator(self, locator):
        self._divider.set_locator(locator)

    def get_axes_locator(self):
        return self._divider.get_locator()

    def get_vsize_hsize(self):

        return self._divider.get_vsize_hsize()
#         from axes_size import AddList

#         vsize = AddList(self._divider.get_vertical())
#         hsize = AddList(self._divider.get_horizontal())

#         return vsize, hsize


class ImageGrid(Grid):
    """
    A class that creates a grid of Axes. In matplotlib, the axes
    location (and size) is specified in the normalized figure
    coordinates. This may not be ideal for images that needs to be
    displayed with a given aspect ratio.  For example, displaying
    images of a same size with some fixed padding between them cannot
    be easily done in matplotlib. ImageGrid is used in such case.
    """

    _defaultCbarAxesClass = CbarAxes

    def __init__(self, fig,
                 rect,
                 nrows_ncols,
                 ngrids=None,
                 direction="row",
                 axes_pad=0.02,
                 add_all=True,
                 share_all=False,
                 aspect=True,
                 label_mode="L",
                 cbar_mode=None,
                 cbar_location="right",
                 cbar_pad=None,
                 cbar_size="5%",
                 cbar_set_cax=True,
                 axes_class=None,
                 ):
        """
        Parameters
        ----------
        fig : `.Figure`
            The parent figure.
        rect : (float, float, float, float) or int
            The axes position, as a ``(left, bottom, width, height)`` tuple or
            as a three-digit subplot position code (e.g., "121").
        direction : {"row", "column"}, default: "row"
        axes_pad : float or (float, float), default: 0.02
            Padding or (horizontal padding, vertical padding) between axes, in
            inches.
        add_all : bool, default: True
        share_all : bool, default: False
        aspect : bool, default: True
        label_mode : {"L", "1", "all"}, default: "L"
            Determines which axes will get tick labels:

            - "L": All axes on the left column get vertical tick labels;
              all axes on the bottom row get horizontal tick labels.
            - "1": Only the bottom left axes is labelled.
            - "all": all axes are labelled.

        cbar_mode : {"each", "single", "edge", None }, default: None
        cbar_location : {"left", "right", "bottom", "top"}, default: "right"
        cbar_pad : float, default: None
        cbar_size : size specification (see `.Size.from_any`), default: "5%"
        cbar_set_cax : bool, default: True
            If True, each axes in the grid has a *cax* attribute that is bound
            to associated *cbar_axes*.
        axes_class : subclass of `matplotlib.axes.Axes`, default: None
        """
        self._nrows, self._ncols = nrows_ncols

        if ngrids is None:
            ngrids = self._nrows * self._ncols
        else:
            if not 0 < ngrids <= self._nrows * self._ncols:
                raise Exception

        self.ngrids = ngrids

        self._init_axes_pad(axes_pad)

        self._colorbar_mode = cbar_mode
        self._colorbar_location = cbar_location
        if cbar_pad is None:
            # horizontal or vertical arrangement?
            if cbar_location in ("left", "right"):
                self._colorbar_pad = self._horiz_pad_size.fixed_size
            else:
                self._colorbar_pad = self._vert_pad_size.fixed_size
        else:
            self._colorbar_pad = cbar_pad

        self._colorbar_size = cbar_size

        cbook._check_in_list(["column", "row"], direction=direction)
        self._direction = direction

        if axes_class is None:
            axes_class = self._defaultAxesClass

        kw = dict(horizontal=[], vertical=[], aspect=aspect)
        if isinstance(rect, (str, Number, SubplotSpec)):
            self._divider = SubplotDivider(fig, rect, **kw)
        elif len(rect) == 3:
            self._divider = SubplotDivider(fig, *rect, **kw)
        elif len(rect) == 4:
            self._divider = Divider(fig, rect, **kw)
        else:
            raise Exception("")

        rect = self._divider.get_position()

        axes_array = np.full((self._nrows, self._ncols), None, dtype=object)
        for i in range(self.ngrids):
            col, row = self._get_col_row(i)
            if share_all:
                sharex = sharey = axes_array[0, 0]
            else:
                sharex = axes_array[0, col]
                sharey = axes_array[row, 0]
            axes_array[row, col] = axes_class(
                fig, rect, sharex=sharex, sharey=sharey)
        self.axes_all = axes_array.ravel().tolist()
        self.axes_column = axes_array.T.tolist()
        self.axes_row = axes_array.tolist()
        self.axes_llc = self.axes_column[0][-1]

        self.cbar_axes = [
            self._defaultCbarAxesClass(fig, rect,
                                       orientation=self._colorbar_location)
            for _ in range(self.ngrids)]

        self._update_locators()

        if add_all:
            for ax in self.axes_all+self.cbar_axes:
                fig.add_axes(ax)

        if cbar_set_cax:
            if self._colorbar_mode == "single":
                for ax in self.axes_all:
                    ax.cax = self.cbar_axes[0]
            elif self._colorbar_mode == "edge":
                for index, ax in enumerate(self.axes_all):
                    col, row = self._get_col_row(index)
                    if self._colorbar_location in ("left", "right"):
                        ax.cax = self.cbar_axes[row]
                    else:
                        ax.cax = self.cbar_axes[col]
            else:
                for ax, cax in zip(self.axes_all, self.cbar_axes):
                    ax.cax = cax

        self.set_label_mode(label_mode)

    def _update_locators(self):

        h = []
        v = []

        h_ax_pos = []
        h_cb_pos = []
        if (self._colorbar_mode == "single" and
             self._colorbar_location in ('left', 'bottom')):
            if self._colorbar_location == "left":
                sz = Size.Fraction(self._nrows, Size.AxesX(self.axes_llc))
                h.append(Size.from_any(self._colorbar_size, sz))
                h.append(Size.from_any(self._colorbar_pad, sz))
                locator = self._divider.new_locator(nx=0, ny=0, ny1=-1)
            elif self._colorbar_location == "bottom":
                sz = Size.Fraction(self._ncols, Size.AxesY(self.axes_llc))
                v.append(Size.from_any(self._colorbar_size, sz))
                v.append(Size.from_any(self._colorbar_pad, sz))
                locator = self._divider.new_locator(nx=0, nx1=-1, ny=0)
            for i in range(self.ngrids):
                self.cbar_axes[i].set_visible(False)
            self.cbar_axes[0].set_axes_locator(locator)
            self.cbar_axes[0].set_visible(True)

        for col, ax in enumerate(self.axes_row[0]):
            if h:
                h.append(self._horiz_pad_size)

            if ax:
                sz = Size.AxesX(ax, aspect="axes", ref_ax=self.axes_all[0])
            else:
                sz = Size.AxesX(self.axes_all[0],
                                aspect="axes", ref_ax=self.axes_all[0])

            if (self._colorbar_mode == "each" or
                    (self._colorbar_mode == 'edge' and
                        col == 0)) and self._colorbar_location == "left":
                h_cb_pos.append(len(h))
                h.append(Size.from_any(self._colorbar_size, sz))
                h.append(Size.from_any(self._colorbar_pad, sz))

            h_ax_pos.append(len(h))

            h.append(sz)

            if ((self._colorbar_mode == "each" or
                    (self._colorbar_mode == 'edge' and
                        col == self._ncols - 1)) and
                    self._colorbar_location == "right"):
                h.append(Size.from_any(self._colorbar_pad, sz))
                h_cb_pos.append(len(h))
                h.append(Size.from_any(self._colorbar_size, sz))

        v_ax_pos = []
        v_cb_pos = []
        for row, ax in enumerate(self.axes_column[0][::-1]):
            if v:
                v.append(self._vert_pad_size)

            if ax:
                sz = Size.AxesY(ax, aspect="axes", ref_ax=self.axes_all[0])
            else:
                sz = Size.AxesY(self.axes_all[0],
                                aspect="axes", ref_ax=self.axes_all[0])

            if (self._colorbar_mode == "each" or
                    (self._colorbar_mode == 'edge' and
                        row == 0)) and self._colorbar_location == "bottom":
                v_cb_pos.append(len(v))
                v.append(Size.from_any(self._colorbar_size, sz))
                v.append(Size.from_any(self._colorbar_pad, sz))

            v_ax_pos.append(len(v))
            v.append(sz)

            if ((self._colorbar_mode == "each" or
                    (self._colorbar_mode == 'edge' and
                        row == self._nrows - 1)) and
                        self._colorbar_location == "top"):
                v.append(Size.from_any(self._colorbar_pad, sz))
                v_cb_pos.append(len(v))
                v.append(Size.from_any(self._colorbar_size, sz))

        for i in range(self.ngrids):
            col, row = self._get_col_row(i)
            locator = self._divider.new_locator(nx=h_ax_pos[col],
                                                ny=v_ax_pos[self._nrows-1-row])
            self.axes_all[i].set_axes_locator(locator)

            if self._colorbar_mode == "each":
                if self._colorbar_location in ("right", "left"):
                    locator = self._divider.new_locator(
                        nx=h_cb_pos[col], ny=v_ax_pos[self._nrows - 1 - row])

                elif self._colorbar_location in ("top", "bottom"):
                    locator = self._divider.new_locator(
                        nx=h_ax_pos[col], ny=v_cb_pos[self._nrows - 1 - row])

                self.cbar_axes[i].set_axes_locator(locator)
            elif self._colorbar_mode == 'edge':
                if ((self._colorbar_location == 'left' and col == 0) or
                        (self._colorbar_location == 'right'
                         and col == self._ncols-1)):
                    locator = self._divider.new_locator(
                        nx=h_cb_pos[0], ny=v_ax_pos[self._nrows - 1 - row])
                    self.cbar_axes[row].set_axes_locator(locator)
                elif ((self._colorbar_location == 'bottom' and
                       row == self._nrows - 1) or
                        (self._colorbar_location == 'top' and row == 0)):
                    locator = self._divider.new_locator(nx=h_ax_pos[col],
                                                        ny=v_cb_pos[0])
                    self.cbar_axes[col].set_axes_locator(locator)

        if self._colorbar_mode == "single":
            if self._colorbar_location == "right":
                sz = Size.Fraction(self._nrows, Size.AxesX(self.axes_llc))
                h.append(Size.from_any(self._colorbar_pad, sz))
                h.append(Size.from_any(self._colorbar_size, sz))
                locator = self._divider.new_locator(nx=-2, ny=0, ny1=-1)
            elif self._colorbar_location == "top":
                sz = Size.Fraction(self._ncols, Size.AxesY(self.axes_llc))
                v.append(Size.from_any(self._colorbar_pad, sz))
                v.append(Size.from_any(self._colorbar_size, sz))
                locator = self._divider.new_locator(nx=0, nx1=-1, ny=-2)
            if self._colorbar_location in ("right", "top"):
                for i in range(self.ngrids):
                    self.cbar_axes[i].set_visible(False)
                self.cbar_axes[0].set_axes_locator(locator)
                self.cbar_axes[0].set_visible(True)
        elif self._colorbar_mode == "each":
            for i in range(self.ngrids):
                self.cbar_axes[i].set_visible(True)
        elif self._colorbar_mode == "edge":
            if self._colorbar_location in ('right', 'left'):
                count = self._nrows
            else:
                count = self._ncols
            for i in range(count):
                self.cbar_axes[i].set_visible(True)
            for j in range(i + 1, self.ngrids):
                self.cbar_axes[j].set_visible(False)
        else:
            for i in range(self.ngrids):
                self.cbar_axes[i].set_visible(False)
                self.cbar_axes[i].set_position([1., 1., 0.001, 0.001],
                                               which="active")

        self._divider.set_horizontal(h)
        self._divider.set_vertical(v)


AxesGrid = ImageGrid