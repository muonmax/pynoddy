import sys, os, platform

import pynoddy
from pynoddy.experiment import Experiment

class MonteCarlo(Experiment):
    '''
    Perform Monte Carlo simulations on a model using defined input statistics
    '''
        
    def __init__(self, history, parameters, base_name="out"):
        '''
        Initialises a Monte Carlo experiment.
        
        **Arguments**:
         - *history* = The .his file this experiment is based on
         - *parameters* = A string pointing to a csv file defining the statistical
                          properties of the model properties being varied, or alternatively an array 
                          of python dictionaries with the same function. This file/dictionary array
                          should have collumns/keys defining:
                              1) the event and parameter being varied (titled 'event' and 'parameter')
                              2) the statistical distribution to sample from (titled 'type' and containing either 'normal',
                                 'vonmises' or 'uniform')
                              3) the distribution mean (titled 'mean') and,
                              4) a collumn defining the distance between the 2.5th and 97.5th percentiles 
                                 (titled '+-') OR one defining the standard deviation (titled 'stdev')
        '''
        
        super(Experiment, self).__init__(history) #initialise
        
        
        if isinstance(parameters,str): #if parameters is a file path
            self.load_parameter_file(parameters)
        else:
            print "Error: parameter dictionares are not yet implemented"
        
        self.basename = base_name
        
    @staticmethod
    def generate_models_from_existing_histories(path,**kwds):
        '''
        Processes all existing his files in the given directory
        
        **Arguments**:
         - *path* = The directory that will be searched for .his files
        **Optional Kewords**:
         - *threads* = The number of seperate threads to run when generating noddy models. For optimum
                       performance this should equal the number of logical cores - 1, unless RAM is a 
                       limiting factor (at this point every thread requires at least 2Gb of ram).
        - *sim_type* = The type of simulation to run. This can be any of: 'BLOCK', 'GEOPHYSICS', 'SURFACES', 
                       'BLOCK_GEOPHYS', 'TOPOLOGY', 'BLOCK_SURFACES', 'ALL'. Default is 'BLOCK'.
        - *force_recalculate* = Forces the recalculation of existing noddy files. Default is False, hence this
                       function will not run history files that are already associated with Noddy data files.
        - *verbose* = True if this function sends output to the print buffer. Default is True.
        '''
        
        #get keywords
        vb = kwds.get("verbose",True)
        stype = kwds.get("sim_type","BLOCK")
        threads = kwds.get("threads",1)
        force = kwds.get("force_recalculate",False)
        
        if threads >= 1: #spawn threads
            
            #gather list of his files
            his_files = []
            for root, dirnames, filenames in os.walk(path): #walk the directory
                for f in filenames:
                    if ('.his' in f): #find all topology files with correct basename
                        his_files.append(os.path.join(root,f))
                        
            #spawn threads untill finished
            from threading import Thread
            thread_list = []            

            while len(his_files) > 0:
                for n in range(0,threads):
                    if len(his_files) > 0:
                        #get path
                        p = his_files[0]
                        his_files.remove(p)
                        
                        #initialise thread
                        t = Thread(target=MonteCarlo.generate_models_from_existing_histories,args=(p,),kwargs={'threads' : 0, 'sim_type' : stype, 'verbose' : vb,'force_recalculate' : force})
                        thread_list.append(t)
                        
                        #start thread
                        t.start()
                                
                #now wait for threads to finish
                for t in thread_list:
                    t.join()
            
        else: #run given file
            output = path.split('.')[0]
            
            #call noddy
            if force or not os.path.exists(output+".g01"): #if noddy files don't exist, or force is true
                if vb:
                    print("Running %s... " % output)
                    print(pynoddy.compute_model(path, output, sim_type = stype))
                    print ("Complete.")
                else:
                    pynoddy.compute_model(path,output, sim_type = stype) 
                    
            #call topology if in TOPOLOGY mode
            if 'TOPOLOGY' in stype:
                if force or not os.path.exists(output+".g23"): #if topology files don't exist, or force is true
                    if vb:
                        print("Running topology on %s... " % output)
                        print(pynoddy.compute_topology(output))
                        print ("Complete.")
                    else:
                        pynoddy.compute_topology(output)
                elif vb:
                    print "Topology files alread exist for %s. Skipping." % path
            
            #flush print buffer
            sys.stdout.flush()   
        
    def generate_model_instances(self, path, count, **kwds):
        '''
        Generates the specified of randomly varied Noddy models.
        
        **Arguments**:
         - *path* = The directory that Noddy models should be generated in
         - *count* = The number of random variations to generate
        **Optional Kewords**:
         - *threads* = The number of seperate threads to run when generating noddy models. Note that RAM is 
                       often a limiting factor (at this point every thread requires at least ~1Gb of ram).
        - *sim_type* = The type of simulation to run. This can be any of: 'BLOCK', 'GEOPHYSICS', 'SURFACES', 
                       'BLOCK_GEOPHYS', 'TOPOLOGY', 'BLOCK_SURFACES', 'ALL'. Default is 'BLOCK'.
        - *write_changes* = A file (path) to write the parameters used in each model realisation to (minus the extension). 
                       The default is a file called 'parameters.csv'. Set as None to disable writing.
        - *verbose* = True if this function sends output to the print buffer. Default is True.
        '''
        
        #get args
        vb = kwds.get("verbose",True)
        stype = kwds.get("sim_type","BLOCK")
        threads = kwds.get("threads",1)
        changes = kwds.get("write_changes","parameters")
        
        #get start time (for timing runs)
        if vb:
            import time
            start_time = time.time()
        
        
        #calculate & create node directory (for multi-node instances)  
        nodename = ""
        if (platform.system() == 'Linux'): #running linux - might be a cluster, so get node name
            nodename = os.uname()[1] #the name of the node it is running on (linux only)
        
        #move into node subdirectory
        path = os.path.join(path,nodename)
        
        #ensure directory exists
        if not os.path.isdir(path):
            os.makedirs(path)
                
        if threads > 1: #multithreaded - spawn required number of threads
            #import thread
            from threading import Thread
            
            thread_list = []
            for t in range(0,threads):
                
                #create subdirectory for this thread
                threadpath=os.path.join(path,"thread_%d" % t)
                if not os.path.isdir(threadpath):
                    os.mkdir(threadpath)
                    
                #make copy of this object 
                import copy
                t_his = copy.deepcopy(self)
                    
                #calculate number of models to run in this thread
                n = count / threads
                if (t == 0): #first thread gets remainder
                    n = n + count % threads
                
                #calculate changes path
                change_path = None
                if not changes is None:
                    change_path = "%s_thread%d" % (changes,t)
                
                #initialise thread
                t = Thread(target=t_his.generate_model_instances,args=(threadpath,n),kwargs={'sim_type' : stype, 'verbose' : vb, 'write_changes' : change_path})
                
                thread_list.append(t)
                
                #start thread
                t.start()
                
                #thread.start_new_thread(t_his.generate_model_instances,(threadpath,n),{'sim_type' : stype, 'verbose' : vb})
                
            #now wait for threads to finish
            for t in thread_list:
                t.join()
                
            #now everything is finished!
            if vb:
                print "Finito!"
                
                elapsed = time.time() - start_time
                print "Generated %d models in %d seconds\n\n" % (count,elapsed)
                
        else: #only 1 thread (or instance of a thread), so run noddy
            for n in range(1,count+1): #numbering needs to start at 1 for topology
                #calculate filename & output path
                outputfile = "%s_%04d" % (self.basename,n)
                outputpath = os.path.join(path,outputfile)
                
                if vb:
                    print "Constructing %s... " % outputfile
                    
                #do random perturbation
                self.random_perturbation(verbose=vb)
                
                #save history
                self.write_history(outputpath + ".his")
                
                #run noddy
                if vb:
                    print("Complete.\nRunning %s... " % outputfile)
                    print(pynoddy.compute_model(outputpath + ".his",outputpath, sim_type = stype))
                    print ("Complete.")
                else:
                    pynoddy.compute_model(outputpath + ".his",outputpath, sim_type = stype)
                
                #run topology if necessary
                if "TOPOLOGY" in stype:
                    if vb:
                        print("Complete. Calculating Topology... ")
                        print(pynoddy.compute_topology(outputpath))
                        print ("Complete.")
                    else:
                        pynoddy.compute_topology(outputpath)
                        
                #flush print buffer
                sys.stdout.flush()
                   
            #write changes
            if not (changes is None):
                print "Writing parameter changes to %s..." % (changes + ".csv")
                self.write_parameter_changes(changes+".csv")
                print "Complete."
            
    @staticmethod
    def load_topology_realisations(path,**args):
        '''
        Loads all model topology realisations and returns them as an array of NoddyTopology objects
        
        **Arguments**:
         - *path* = The root directory that models should be loaded from. All models with the same base_name
                    as this class will be loaded (including subdirectoriess)
        **Optional Arguments**:
         - *verbose* = True if this function should write debug information to the print buffer. Default is True.
         
        **Returns**:
         - a list of NoddyTopology objects
        '''
        
        vb = args.get('verbose',True)
        
        if vb:
            print "Loading models in %s" % path
        
        #array of topology objects
        from pynoddy.output import NoddyTopology
        topologies = []        
        
        for root, dirnames, filenames in os.walk(path): #walk the directory
            for f in filenames:
                if ('.g23' in f): #find all topology files
                    base = os.path.join(root,f.split('.')[0])
                    if vb:
                        print 'Loading %s' % base
                        
                    #load & store topology 
                    topologies.append(NoddyTopology(base))
          
        return topologies
         
    @staticmethod
    def load_noddy_realisations(path,**args):
        '''
        Loads all model realisations and returns them as an array of NoddyOutput objects
        
        **Arguments**:
         - *path* = The root directory that models should be loaded from. All models with the same base_name
                    as this class will be loaded (including subdirectoriess)
                    
        **Optional Arguments**:
         - *verbose* = True if this function should write debug information to the print buffer. Default is True.
        **Returns**:
         - a list of NoddyOutput objects
        '''
        
        vb = args.get('verbose',True)
        
        #TODO
        print "Error: load_noddy_realisations has not been implemented yet. Sorry."
        
if __name__ == '__main__':
        
    #load pynoddy
    sys.path.append(r"C:\Users\Sam\SkyDrive\Documents\Masters\pynoddy")
    import pynoddy
    
    #setup
    pynoddy.ensure_discrete_volumes = True
    
    ###################################################
    #MONTE CARLO PERTURBATION OF HIS FILE EXAMPLE
    ###################################################
    
    #setup working directory
    os.chdir(r'C:\Users\Sam\SkyDrive\Documents\Masters\Models\Primitive\monte carlo test')
    his_file = "foldUC.his"
    params_file = "foldUC_params.csv"
    
    #create new MonteCarlo experiment
    mc = MonteCarlo(his_file,params_file)
    
    #generate 100 random perturbations using 4 separate threads (in TOPOLOGY mode)
    output_name = "mc_out"
    n = 1000
    mc.generate_model_instances(output_name,n,sim_type="TOPOLOGY",threads=4)
    
    #load output
    topologies = MonteCarlo.load_topology_realisations(output_name, verbose=True)
    
    #calculate unique topologies
    from pynoddy.output import NoddyTopology
    uTopo = NoddyTopology.calculate_unique_topologies(topologies,output="accumulate.csv")
    print "%d unique topologies found in %d simulations" % (len(uTopo),n)
    
#    ###################################################
#    #run existing .his files example (in TOPOLOGY mode)
#    ###################################################
#    
#    #setup working environment
#    os.chdir(r'C:\Users\Sam\SkyDrive\Documents\Masters\Models\Primitive\monte carlo test')
#    path = 'multi_his_test'
#    basename='GBasin123_random_draw'
#    
#    #run noddy in 'TOPOLOGY' mode (multithreaded)
#    MonteCarlo.generate_models_from_existing_histories(path,threads=6,sim_type="TOPOLOGY",force_recalculate=True)    
#    
#    #calculate topologies (single thread)
#    #MonteCarlo.generate_topologies_from_existing_histories(path,basename,verbose=True)
#          
#    #load topology output
#    topologies = MonteCarlo.load_topology_realisations(path, verbose=True)
#    
#    #calculate unique topologies
#    from pynoddy.output import NoddyOutput
#    uTopo = NoddyOutput.calculate_unique_topologies(topologies,output="accumulate.csv")
#    print "%d unique topologies found in %s" % (len(uTopo),path)
#    