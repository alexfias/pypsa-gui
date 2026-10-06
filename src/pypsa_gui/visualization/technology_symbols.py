"""Original vector pictograms, not an IEC-certified symbol set."""
import re
import math
from matplotlib.patches import Circle, Rectangle, Polygon


def technology(component, carrier):
    value = re.sub(r'[^a-z0-9]+', ' ', str(carrier).lower()).strip()
    tokens = set(value.split())
    if component == 'loads': return 'load'
    if component == 'shunt_impedances': return 'shunt'
    if component in ('stores', 'storage_units'):
        if tokens & {'battery', 'bat', 'bess'}: return 'battery'
        if tokens & {'phs', 'pumped', 'pumping'}: return 'pumped hydro'
        return 'storage'
    if component != 'generators': return 'generator'
    if tokens & {'onwind', 'offwind', 'wind'}: return 'wind'
    if tokens & {'solar', 'pv', 'photovoltaic'}: return 'solar'
    if tokens & {'hydro', 'ror', 'runofriver'}: return 'hydro'
    if tokens & {'ocgt', 'ccgt', 'gas'}: return 'gas'
    if tokens & {'coal', 'lignite'}: return 'coal'
    if tokens & {'biomass', 'biogas'}: return 'biomass'
    if tokens & {'nuclear', 'uranium'}: return 'nuclear'
    return 'generator'


def draw_symbol(ax, x, y, component, carrier='', mode='Technology', color='#3d876c'):
    """Return all vector artists so callers can attach picking/tooltips."""
    kind = technology(component, carrier)
    if mode == 'Electrical':
        kind = {'generators':'generator', 'loads':'load',
                'shunt_impedances':'shunt'}.get(component, 'storage')
        color = '#334155'
    artists = []
    def patch(p):
        p.set_zorder(4); ax.add_patch(p); artists.append(p)
    def line(xs, ys, **kw):
        a, = ax.plot([x+t for t in xs], [y+t for t in ys],
                     color=color, linewidth=1.6, zorder=5, **kw)
        artists.append(a)
    def text(label, size=9):
        artists.append(ax.text(x,y,label,ha='center',va='center',fontsize=size,
                               color='#253746',zorder=6))
    # White backing keeps the connection from running through a pictogram.
    patch(Rectangle((x-.48,y-.43),.96,.86,facecolor='white',edgecolor='none'))
    top = {'wind': .46, 'solar': .28, 'hydro': .39, 'pumped hydro': .39,
           'battery': .25, 'load': .24, 'shunt': .4, 'storage': .29}.get(kind, .34)
    if top < .43:
        line([0, 0], [.43, top])
    if kind == 'wind':
        line([0,0],[-.37,.10])
        for angle in (90,210,330):
            theta=math.radians(angle)
            line([0,.36*math.cos(theta)],[.1,.1+.36*math.sin(theta)])
        patch(Circle((x,y+.1),.045,facecolor=color,edgecolor=color))
        line([-.17,.17],[-.37,-.37])
    elif kind == 'solar':
        patch(Polygon([(x-.4,y-.15),(x+.3,y-.15),(x+.42,y+.28),(x-.28,y+.28)],
                      facecolor='#edf5fa',edgecolor=color,linewidth=1.5))
        for offset in (-.17,.06): line([offset,offset+.12],[-.15,.28])
        line([-.34,.36],[.06,.06]); line([0,0],[-.15,-.34]); line([-.22,.22],[-.34,-.34])
    elif kind in ('hydro','pumped hydro'):
        patch(Polygon([(x,y+.39),(x-.27,y-.04),(x-.22,y-.25),(x,y-.32),
                       (x+.22,y-.25),(x+.27,y-.04)],facecolor='#edf7fb',edgecolor=color,linewidth=1.5))
        text('P' if kind=='pumped hydro' else '~')
    elif kind == 'battery':
        patch(Rectangle((x-.36,y-.25),.72,.5,facecolor='white',edgecolor=color,linewidth=1.5))
        patch(Rectangle((x+.36,y-.1),.09,.2,facecolor=color,edgecolor=color))
        line([-.24,-.08],[0,0]); line([-.16,-.16],[-.08,.08]); line([.1,.26],[0,0])
    elif kind == 'load':
        patch(Polygon([(x-.26,y+.24),(x+.26,y+.24),(x,y-.3)],facecolor='white',edgecolor=color,linewidth=1.5))
    elif kind == 'shunt':
        line([0,0],[.4,.1]); line([-.23,.23],[.1,.1]); line([-.23,.23],[-.05,-.05])
        line([0,0],[-.05,-.3]); line([-.23,.23],[-.3,-.3])
        line([-.15,.15],[-.38,-.38])
    elif kind == 'storage':
        patch(Rectangle((x-.37,y-.29),.74,.58,facecolor='#edf4f7',edgecolor=color,linewidth=1.5))
        text('E')
    else:
        patch(Circle((x,y),.34,facecolor='white',edgecolor=color,linewidth=1.6))
        text({'gas':'GAS','coal':'COAL','biomass':'BIO','nuclear':'NUC'}.get(kind,'G'),
             size=7 if kind != 'generator' else 10)
    return artists
