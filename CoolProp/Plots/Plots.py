# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import

import numpy, matplotlib, matplotlib.pyplot, math, re
from scipy.interpolate import interp1d

import CoolProp.CoolProp as CP

from scipy import interpolate
from scipy.spatial.kdtree import KDTree
import warnings
from CoolProp.Plots.Common import IsoLine,BasePlot
import CoolProp
import sys
from CoolProp.Plots.SimpleCycles import StatePoint, StateContainer,\
    SimpleRankineCycle



class PropertyPlot(BasePlot):
    def __init__(self, fluid_name, graph_type, **kwargs):
        """
        Create graph for the specified fluid properties

        Parameters
        ----------
        fluid_name : string or AbstractState
            The name of the fluid to be plotted or a state instance
        graph_type : string
            The graph type to be plotted, like \"PH\" or \"TS\"
        axis : :func:`matplotlib.pyplot.gca()`, Optional
            The current axis system to be plotted to.
            Default: create a new axis system
        fig : :func:`matplotlib.pyplot.figure()`, Optional
            The current figure to be plotted to.
            Default: create a new figure
        unit_system : string, ['EUR','KSI','SI']
            Select the units used for the plotting.  'EUR' is bar, kJ, C; 'KSI' is kPa, kJ, K; 'SI' is Pa, J, K
        reciprocal_density : bool
            NOT IMPLEMENTED: If True, 1/rho will be plotted instead of rho 

        Examples
        --------
        >>> from CoolProp.Plots import PropertyPlot
        >>> plot = PropertyPlot('Water', 'Ts')
        >>> plot.show()

        >>> plot = PropertyPlot('HEOS::n-Pentane', 'ph')
        >>> plot.calc_isolines(CoolProp.iQ,[0.0,1.0],num=11)
        >>> Ts_lim = plot.get_axis_limits(CoolProp.iT, CoolProp.iSmass)
        >>> plot.calc_isolines(CoolProp.iT,Ts_lim[0:2])
        >>> plot.calc_isolines(CoolProp.iSmass,Ts_lim[2:4])
        >>> plot.savefig('pentane_ph.pdf')

        .. note::

            See the online documentation for a list of the available fluids and
            graph types
        """
        super(PropertyPlot, self).__init__(fluid_name, graph_type, **kwargs)
        self._isolines = {} 
        #self._plines = {}
        #self._ppoints = {}
        self.get_axis_limits()
        self._plot_default_annotations()
        
    @property
    def isolines(self): return self._isolines
    #@property
    #def plines(self): return self._plines
    #@property
    #def ppoints(self): return self._ppoints
    
    def show(self):
        self.draw()
        super(PropertyPlot, self).show()
        
    def savefig(self, *args, **kwargs):
        self.draw()
        super(PropertyPlot, self).savefig(*args, **kwargs)
    
    def _plotRound(self, values):
        """
        A function round an array-like object while maintaining the
        amount of entries. This is needed for the isolines since we
        want the labels to look pretty (=rounding), but we do not
        know the spacing of the lines. A fixed number of digits after
        rounding might lead to reduced array size.
        """
        inVal   = numpy.unique(numpy.sort(numpy.array(values)))
        output  = inVal[1:] * 0.0
        digits  = -1
        limit   = 10
        lim     = inVal * 0.0 + 10
        # remove less from the numbers until same length,
        # more than 10 significant digits does not really
        # make sense, does it?
        while len(inVal) > len(output) and digits < limit:
            digits += 1
            val     = ( numpy.around(numpy.log10(numpy.abs(inVal))) * -1) + digits + 1
            val     = numpy.where(val < lim, val,  lim)
            val     = numpy.where(val >-lim, val, -lim)
            output  = numpy.zeros(inVal.shape)
            for i in range(len(inVal)):
                output[i] = numpy.around(inVal[i],decimals=int(val[i]))
            output = numpy.unique(output)
        return output
        
    def calc_isolines(self, iso_type, iso_range, num=15, rounding=False, points=200):
        """Calculate lines with constant values of type 'iso_type' in terms of x and y as
        defined by the plot object. 'iso_range' either is a collection of values or 
        simply the minimum and maximum value between which 'num' lines get calculated.
        The 'rounding' parameter can be used to generate prettier labels if needed.
        """
        
        if iso_range is None or (len(iso_range) == 1 and num != 1):
            raise ValueError('Automatic interval detection for isoline \
                              boundaries is not supported yet, use the \
                              iso_range=[min, max] parameter.')
 
        if len(iso_range) == 2 and num is None:
            raise ValueError('Please specify the number of isoline you want \
                              e.g. num=10')

        if iso_type == 'all':
            for i_type in IsoLine.XY_SWITCH:
                if IsoLine.XY_SWITCH[i_type].get(self.y_index*10+self.x_index,None) is not None:
                    # TODO implement the automatic interval detection.
                    limits = self._get_axis_limits(i_type, CoolProp.iT)
                    self.calc_isolines(i_type, [limits[0],limits[1]], num, rounding, points)
            return 
                    
        iso_range = numpy.sort(numpy.unique(iso_range))
        # Generate iso ranges
        if len(iso_range) == 2:
            iso_range = self.generate_ranges(iso_type, iso_range[0], iso_range[1], num)
        if rounding:
            iso_range = self._plotRound(iso_range)
        
        # Limits are alreadyin SI units
        limits = self._get_axis_limits()
        
        ixrange = self.generate_ranges(self._x_index,limits[0],limits[1],points)
        iyrange = self.generate_ranges(self._y_index,limits[2],limits[3],points)
        
        dim = self._system[iso_type]
        
        lines  = self.isolines.get(iso_type, [])
        for i in range(num):
            lines.append(IsoLine(iso_type,self._x_index,self._y_index, value=dim.to_SI(iso_range[i]), state=self._state))
            lines[-1].calc_range(ixrange,iyrange)
            lines[-1].sanitize_data()
        self.isolines[iso_type] = lines 
        return 
    
    
    def draw_isolines(self):
        for i in self.isolines:
            props = self.props[i]
            dimx = self._system[self._x_index]
            dimy = self._system[self._y_index]
            for line in self.isolines[i]:
                if line.i_index == CoolProp.iQ and \
                  (line.value == 0.0 or line.value == 1.0):
                    plot_props = props.copy()
                    if 'lw' in plot_props: plot_props['lw'] *= 2.0
                    else: plot_props['lw'] = 1.0
                    if 'alpha' in plot_props: plot_props['alpha'] *= 2.0
                    else: plot_props['alpha'] = 1.0
                else:
                    plot_props = props
                self.axis.plot(dimx.from_SI(line.x),dimy.from_SI(line.y),**plot_props)
    
    def draw(self):
        self.draw_isolines()
        
    #def label_isolines(self, dx=0.075, dy=0.100):
    #    [xmin, xmax, ymin, ymax] = self.get_axis_limits()
    #    for i in self.isolines:
    #         for line in self.isolines[i]:
    #             if self.get_x_y_dydx(xv, yv, x)
             
         
                
                
    def draw_process(self, statecontainer, points=None, line_opts={'color' : 'r', 'lw' : 1.5}):
        """ Draw process or cycle from x and y values in axis units

        Parameters
        ----------
        statecontainer : CoolProp.Plots.SimpleCycles.StateContainer()
            A state container object that contains all the information required to draw the process.
            Note that points that appear several times get added to a special of highlighted points.
        line_opts : dict
            Line options (please see :func:`matplotlib.pyplot.plot`), optional
            Use this parameter to pass a label for the legend.
        """
        warnings.warn("You called the function \"draw_process\", which is not tested.",UserWarning)
        
        
        dimx = self.system[self.x_index]
        dimy = self.system[self.y_index]
        
        if points is None: points = StateContainer()
        
        xdata = []
        ydata = []        
        old = statecontainer[len(statecontainer)-1]
        for i in statecontainer:
            point = statecontainer[i]
            if point == old: 
                points.append(point)
                old = point
                continue
            xdata.append(point[self.x_index])
            ydata.append(point[self.y_index])
            old = point
        xdata = dimx.from_SI(numpy.asarray(xdata))
        ydata = dimy.from_SI(numpy.asarray(ydata))
        self.axis.plot(xdata,ydata,**line_opts)
        
        xdata = numpy.empty(len(points))
        ydata = numpy.empty(len(points))
        for i in points:
            point = points[i]
            xdata[i] = point[self.x_index]
            ydata[i] = point[self.y_index]
        xdata = dimx.from_SI(numpy.asarray(xdata))
        ydata = dimy.from_SI(numpy.asarray(ydata))
        line_opts['label'] = ''
        line_opts['linestyle'] = 'none'
        line_opts['marker'] = 'o'
        self.axis.plot(xdata,ydata,**line_opts)
        

def InlineLabel(xv,yv,x=None,y=None,axis=None,fig=None):
    warnings.warn("You called the deprecated function \"InlineLabel\", use \"BasePlot.inline_label\".",DeprecationWarning)
    plot = PropertyPlot("water","TS",figure=fig,axis=axis)
    return plot.inline_label(xv,yv,x,y)

class PropsPlot(PropertyPlot):
    def __init__(self, fluid_name, graph_type, units = 'KSI', reciprocal_density = False, **kwargs):
        super(PropsPlot, self).__init__(fluid_name, graph_type, units=units, reciprocal_density=reciprocal_density, **kwargs)
        warnings.warn("You called the deprecated class \"PropsPlot\", use \"PropertyPlot\".",DeprecationWarning)


if __name__ == "__main__":
    #plot = PropertyPlot('HEOS::n-Pentane', 'PH', unit_system='EUR')
    #Ts = plot.get_axis_limits(CoolProp.iT, CoolProp.iSmass)
    #TD = plot.get_axis_limits(CoolProp.iT, CoolProp.iDmass)
    #plot.calc_isolines(CoolProp.iT,     Ts[0:2])
    #plot.calc_isolines(CoolProp.iQ,     [0.0,1.0], num=11)
    #plot.calc_isolines(CoolProp.iSmass, Ts[2:4])
    #plot.calc_isolines(CoolProp.iDmass, TD[2:4])
    #plot.draw_isolines()
    #plot.show()
    #
    pp = PropertyPlot('HEOS::Water', 'TS', unit_system='EUR')
    ph = pp.get_axis_limits(CoolProp.iP, CoolProp.iHmass)
    pp.calc_isolines(CoolProp.iP,     ph[0:2])
    pp.calc_isolines(CoolProp.iHmass, ph[2:4])
    pp.calc_isolines(CoolProp.iQ,     [0.0,1.0], num=11)
    
    cycle = SimpleRankineCycle('HEOS::Water', 'TS', unit_system='EUR')
    T0 = 300
    pp.state.update(CoolProp.QT_INPUTS,0.0,T0+15)
    p0 = pp.state.keyed_output(CoolProp.iP)
    T2 = 700
    pp.state.update(CoolProp.QT_INPUTS,1.0,T2-150)
    p2 = pp.state.keyed_output(CoolProp.iP)
    cycle.simple_solve(T0, p0, T2, p2, 0.7, 0.8, SI=True)
    cycle.steps = 50
    sc = cycle.get_state_changes()
    pp.draw_process(sc)
    #
    cycle.simple_solve(T0-273.15-10, p0/1e5, T2-273.15+50, p2/1e5-5, 0.7, 0.8, SI=False)
    sc2 = cycle.get_state_changes()
    pp.draw_process(sc2, line_opts={'color':'blue', 'lw':1.5})
    #
    pp.show()
    
    #
    #plot.savefig("Plots.pdf")
    #plot.show()
    #for i in plot.isolines:
    #    print(plot.isolines[i][0].x,plot.isolines[i][0].y)
