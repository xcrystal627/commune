


from .module import Module # the module module
M = c = Block = Agent  = Module # alias c.Module as c.Block, c.Lego, c.M
from .vali import Vali # the vali module
from .server import Server, Client # the server module
from .key import Key # the key module
# set the module functions as globalsw
c.add_to_globals(globals())
v = Vali 
s = Server
k = Key
# set the module functions as globals
key = c.get_key # override key function with file key in commune/key.py TODO: remove this line with a better solution