import commune
from ray import tune
from typing import *
import torch
from copy import deepcopy




class Trainer(commune.Module):
    def __init__(self, 
                 model: str = 'model:gptj:train', 
                 tag : str ='base_trainer',
                 metrics_server: str = 'metrics_server' ,
                 tuner: Dict = dict(
                     metric = 'loss',
                     mode = 'min',
                     max_concurrent_trials = 1,
                     resources_per_trial = {"cpu": 2, "gpu": 0},
                     num_samples= 1000
                 ),
                 **kwargs):
        
        
        self.set_config(config = locals())
        self.set_model(self.config['model'])
        self.set_tag(self.config['tag'])
        self.set_metrics_server(self.config['metrics_server'])
        self.set_tuner(**self.config['tuner'])

    def set_config(self, config) -> None:
        self.config = deepcopy(config)
        self.config.pop('self',None)
        self.config.pop('kwargs', None)
        self.config.pop('args', None)
        
        # self.model = self.connect(self.model_name)


        
    def set_model(self, 
                          model:str,
                          refresh:bool = True,
                          timeout:int = 1000,
                          check_step:int= 2):
        # if not self.server_exists(metrics_server):
        wait_time = 0
        while not self.server_exists(model) and wait_time <= timeout:
            self.sleep(check_step)
            wait_time += check_step
            
        if wait_time >= timeout:
            raise Exception('Your peer is not visible')
        
        self.model = model
    
        
    def set_metrics_server(self, 
                          metrics_server:str,
                          refresh:bool = True,
                          timeout:int = 10,
                          check_step:int= 2):
        # if not self.server_exists(metrics_server):
        commune.launch(module='commune.metric.MetricServer', name=metrics_server, refresh=refresh)
        
        wait_time = 0

        while not self.server_exists(metrics_server) and wait_time <= timeout:
            self.sleep(check_step)
            wait_time += check_step
            
        if wait_time >= timeout:
            raise Exception('Timeout')
        self.metrics_server = metrics_server
        # self.metrics_server = self.connect(metrics_server)
        metrics_module = commune.connect(metrics_server)
        metrics_module.refresh()
        metrics_module.set_metric('baseline', 3)
        
    def hyper2params(self, params: Dict) -> Dict:
        return self.flat2deep(params)

    def get_hyperopt_tag(self, config:dict):
        
        tag = f'{self.model}::{self.tag}__'
        for k, v in config.items():
            tag += f'{k}_{v}__'
                
        return tag
 
                
    def objective(self, 
                  hyperparams:dict = None, 
                  train_kwargs = {'num_batches': 100},
                  timeout:int=1000) -> Dict:

        if hyperparams is None:
            hyperparams = {}
            
            
        
        
        params = self.hyper2params(deepcopy(hyperparams))
        params['stats'] = {}
        train_kwargs.update(dict(
            tag=self.tag,
            params = params,
            save = False,
            load = False,
        ))
        
        model = commune.connect(self.model)

        output = model.train_model(**train_kwargs, timeout=timeout)
        
        metric_server = commune.connect(self.metrics_server)
        best_metric = metric_server.best_metric()
        
        is_best = False
        if self.config['tuner']['mode'] == 'min':
            is_best =  bool(output['loss'] <  best_metric)
        elif self.config['tuner']['mode'] == 'max':
            is_best =  bool(output['loss'] >  best_metric)
            
        hyperopt_tag = self.get_hyperopt_tag(hyperparams)

        metric_server.set_metric(hyperopt_tag, output['loss'])
        
    
        model.save(keys=['config'], tag=self.tag)
        
        trial_info_dict =  {**output, **hyperparams}
        
        trial_info_path =f'experiment/{self.model}/{self.tag}/{hyperopt_tag}.json'
        model.save(trial_info_path, keys=['config'])
                
        if is_best:
            model.save(tag=self.tag)
            
        return output
    @classmethod
    def default_search_space(cls):
        search_space = {
            'optimizer.lr': tune.loguniform(1e-6, 1e-4),
            "finetune.num_layers": tune.choice([1,2,3,4,5,6,7]),
            # 'load': tune.choice([True, False]),
        }
        
        return search_space
    
    def set_tuner(self, 
                 resources_per_trial:Dict,
                 max_concurrent_trials:int = 4,
                 num_samples: int = 10,
                 search_space:Dict = None,
                 metric: str = 'loss',
                 mode : str = 'min'):
        
        
        # 2. Define a search space.
        
        self.metric = metric
        self.mode = mode

        self.search_space = search_space if search_space else self.default_search_space()
        
        
            
        self.resources_per_trial = resources_per_trial
        self.objective_with_resources = tune.with_resources(self.objective, self.resources_per_trial)

        self.tune_config = tune.TuneConfig(num_samples=num_samples,
                                           max_concurrent_trials=max_concurrent_trials)
        
        # 3. Start a Tune run and print the best result.
        self.tuner = tune.Tuner(self.objective_with_resources, 
                                param_space=self.search_space, 
                                tune_config=self.tune_config)
    def fit(self, **kwargs):

        results = self.tuner.fit()
        print(results.get_best_result(metric=self.metric, mode=self.mode).config)

    @classmethod
    def test(cls):
        trainer = cls()
        print(trainer.fit())
        
        # print(self.model)
        # print(self.model_name)
        
        
if __name__ == "__main__":
    Trainer.test()
    # dataset = commune.connect('dataset::bittensor')
    
    # print(dataset.module_id)
    # for i in range(10):
    #     print('Alo')
    #     AdapterModel.train(num_batches=1, dataset=dataset)
    #     adapter = dict(
    #                 module='commune.model.adapter.block.AdapterBlock', 
    #                 params = {'in_dim': 10, 'hidden_dim': 64,  'num_layers': 8},
    #                 key2attr = {'in_dim': 'hidden_dim', 'out_dim': 'vocab_size'},
    #                 device = None
    #                 )
    # AdapterModel.run()
    # EnsembleModel.run_neuron()
    # AdapterModel.serve(wait_for_termination=False)
    # AdapterModel.run()
    # print('FUCK')
    # TransformerModel('gptj', tag='demo', load=True).save_pretrained()
    
    # TransformerModel.run()
    # TransformerModel.experiment()


