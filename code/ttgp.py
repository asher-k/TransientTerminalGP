"""
Contains code for the transient-terminal GP algorithm using DEAP.

Written by Asher Stout, 300432820
"""
from deap import base, creator, tools, gp
import operator as op
import random as rand
import shared
import ttsclasses as tts
import ttsfunctions as ttsf

transient = tts.TransientSet(name="transient", arity=1, lifespan=5)


def create_definitions(tb, pset):
    """
    Initializes a variety of parameters using the DEAP creator & toolbox

    :param tb: reference to the DEAP toolbox
    :param pset: the primitive set
    :return:
    """
    # Initialize individual, fitness, and population
    creator.create("MOFitness", base.Fitness, weights=(-1.0, -1.0))
    creator.create("Individual", tts.TransientTree, fitness=creator.MOFitness)
    tb.register("initialize", gp.genHalfAndHalf, pset=pset, min_=1, max_=4)
    tb.register("individual", tools.initIterate, container=creator.Individual, generator=tb.initialize)
    tb.register("population", tools.initRepeat, container=list, func=tb.individual)

    # Register genetic operators & decorate bounds
    tb.register("mate", gp.cxOnePoint)
    tb.decorate("mate", gp.staticLimit(key=op.attrgetter('height'), max_value=90))
    tb.register("expr_mut", gp.genFull, min_=1, max_=3)
    tb.register("mutate", gp.mutUniform, expr=tb.expr_mut, pset=pset)
    tb.decorate("mutate", gp.staticLimit(key=op.attrgetter('height'), max_value=90))
    tb.register("expr_trans_mut", ttsf.genRand)
    tb.register("transient_mutate", ttsf.transientMutUniform, expr=tb.expr_trans_mut, pset=transient)
    tb.decorate("transient_mutate", gp.staticLimit(key=op.attrgetter('height'), max_value=90))

    # Register selection, evaluation, compiliation
    tb.register("selection", tools.selNSGA2)
    tb.register("evaluation", shared.eval_solution, _tb=tb)
    tb.register("compile", gp.compile, pset=pset)
    return


def evolve(data, labels, names, tdata, tlabels, generations=50, pop_size=100, cxpb=0.8, mutpb=0.1, tmutpb=0.1):
    """
    Performs the setup for the main evolutionary process
    :param data: training data to use during evolution
    :param labels: target variables for the training data
    :param names: names for primitives of the data, used for constructing the primitive set
    :param tdata: testing data used during solution evaluation
    :param tlabels: target variables for the testing data
    :param generations: number of generations
    :param pop_size: population size
    :param cxpb: crossover probability
    :param mutpb: mutation probability
    :param tmutpb: transient mutation probability

    :return: the best individual of the evolution & the log
    """
    # Initialize toolbox, population, hof, and logs
    toolbox = base.Toolbox()
    primitives = shared.create_primitives(names, data.shape[1])
    create_definitions(toolbox, primitives)
    pop = toolbox.population(n=pop_size)
    hof = tools.ParetoFront()
    stats, logbook = shared.init_logger("gen", "best")

    # Update initial fitnesses & print log for 0th generation
    fitness = [toolbox.evaluation(function=ind, data=data, actual=labels) for ind in pop]
    for ind, fit in zip([ind for ind in pop if not ind.fitness.valid], fitness):
        ind.fitness.values = fit
    hof.update(pop)
    logbook.record(gen=0, best=toolbox.evaluation(function=shared.getBalancedInd(hof, pop), data=tdata, actual=tlabels),
                   **stats.compile(pop))
    print(logbook.stream)

    # Begin evolution of population
    for g in range(1, generations):
        nextgen = toolbox.selection(pop, len(pop))
        for ind in nextgen:
            ind = ind.update_last()  # Update the metadata on evolution prior to this generation's evolution
        elites = nextgen[0:int(pop_size*0.1)]   # Elites comprise the best 10% of the population
        del nextgen[0:int(pop_size*0.1)]
        nextgen = shared.applyOps(nextgen, toolbox, cxpb, mutpb, tmutpb, (transient.trans_count > 0))
        nextgen = nextgen + elites  # After generation evolution add elites back into population

        # Update fitness & population, update HoF, record generation log
        invalidind = [ind for ind in nextgen if not ind.fitness.valid]
        fitness = [toolbox.evaluation(function=ind, data=data, actual=labels) for ind in invalidind]
        for ind, fit in zip(invalidind, fitness):
            ind.fitness.values = fit
        hof.update(pop)
        pop[:] = nextgen
        logbook.record(gen=g, best=toolbox.evaluation(function=shared.getBalancedInd(hof, pop), data=tdata, actual=tlabels),
                       **stats.compile(pop))
        print(logbook.stream)

        # Update Transient Terminal Set for next generation
        transient.update_set(pop, g)
    return hof[0], logbook
