import commune as c

class AccessSubspace(c.Module):
    sync_time = 0
    def __init__(self, module, **kwargs):
        config = self.set_config(kwargs)
        self.module = module
        self.sync()
        self.user_info = {}


    def sync(self):
        sync_time  = c.time() - self.sync_time
        if sync_time >  self.config.sync_interval :
            self.sync_time = c.time()
            self.subspace = c.module('subspace')(network=self.config.network, netuid=self.config.netuid)
            self.stakes = self.subspace.stakes()
        else:
            return
        

    def verify_staleness(self, input:dict) -> dict:

        # here we want to verify the data is signed with the correct key
        request_staleness = c.timestamp() - input['data'].get('timestamp', 0)
        assert request_staleness < self.config.max_staleness, f"Request is too old, {request_staleness} > MAX_STALENESS ({self.max_request_staleness})  seconds old"
        

    def verify(self, input:dict) -> dict:

        self.verify_staleness(input)

        address = input['address']
        fn = input.get('fn')
        if c.is_admin(address):
            requests = self.requests.get(address, 0) + 1
            self.last_time_called[address] = c.timestamp()
            return input


        # if not an admin address, we need to check the whitelist and blacklist
        assert fn in self.module.whitelist or fn in c.helper_whitelist, f"Function {fn} not in whitelist"
        assert fn not in self.module.blacklist, f"Function {fn} is blacklisted" 

        # RATE LIMIT CHECKING HERE
        self.sync()

        # Calculate the rate limit for the address
        stake = self.stakes.get(address, 0)
        max_rate_limit = (stake / self.config.stake2rate) + self.config.free_rate_limit

        # get the rate limit for the function
        user_info = self.user_info.get(address, {'requests': 0, 'last_time_called': 0})
        address_rate_limit = 1 / (c.time() - user_info['last_time_called'] + 1e-10)
        
        assert requests < rate_limit, f"Rate limit exceeded for {address}, {requests} > {rate_limit} with {stake} stake and stake2rate of {self.config.stake2rate}"

        # update the user info
        user_info['last_time_called'] = c.time()
        user_info['requests'] += 1
        self.user_info[address] = user_info
        return input


    @classmethod
    def test(cls):
        name = 'access_subspace.demo' 
        module = c.serve('module', name=name, wait_for_server=True)
        client = c.connect('module', key='fam')
        c.print(client.info())
        c.kill(name)
        return {'name': name, 'module': module, 'client': client}
        


