'''
fmga
Genetic Algorithms - Objective Function Maximization
Author: Ameya Daigavane
Date: 15th April, 2018
'''

# External library dependencies
from random import randint, uniform
import numpy as np
import pathos.multiprocessing as mp


# Weighted choice function - each choice has a corresponding weight
def weighted_choice(choices, weights):
    normalized_weights = np.array([weight for weight in weights]) / np.sum(weights)
    threshold = uniform(0, 1)
    total = 1

    for index, normalized_weight in enumerate(normalized_weights):
        total -= normalized_weight
        if total < threshold:
            return choices[index]


# Point class and method definitions
class Point:

    # Create random n-dimensional point within boundaries
    def __init__(self, associated_population=None, dimensions=2):

        if associated_population is None:
            self.associated_population = None
            self.boundaries = [(0, 100) for _ in range(dimensions)]
            self.mutation_range = 5
        else:
            self.associated_population = associated_population
            self.boundaries = associated_population.boundaries
            self.mutation_range = associated_population.mutation_range

        # Initialize coordinates uniformly random in range for each dimension
        self.coordinates = np.array([uniform(self.boundaries[dimension][0], self.boundaries[dimension][1]) for dimension in range(dimensions)])

        self.index = -1
        self.fitness = 0.0
        self.diversity = 0.0
        self.fitness_rank = -1
        self.diversity_rank = -1

    # Fitness score - objective function evaluated at the point
    def evaluate_fitness(self, eval_function=None):
        try:
            self.fitness = eval_function(*self.coordinates)
            return self.fitness
        except TypeError:
            print("function passed is invalid.")
            raise

    # Mutation operator
    def mutate(self):
        # Choose an index at random
        index = randint(0, np.size(self.coordinates) - 1)
        self.coordinates[index] += uniform(-self.mutation_range, self.mutation_range)

        # Ensure the point doesn't mutate out of range!
        self.coordinates[index] = min(self.boundaries[index][0], self.coordinates[index])
        self.coordinates[index] = max(self.boundaries[index][1], self.coordinates[index])

    def __repr__(self):
        return repr(self.coordinates)


# Population class and method definition
class Population:
    def __init__(self, objective_function=None, dimensions=None, population_size=60, boundaries=None,
                 elite_fraction=0.1, mutation_probability=0.05, mutation_range=5, verbose=0,
                 multiprocessing=False, processes=8):

        # Data-validation for parameters
        if elite_fraction > 1.0 or elite_fraction < 0.0:
            raise ValueError("Parameter 'elite_fraction' must be in range [0,1].")

        if mutation_probability > 1.0 or mutation_probability < 0.0:
            raise ValueError("Parameter 'mutation_probability' must be in range [0,1].")

        if verbose not in [0, 1, 2]:
            raise ValueError("Parameter verbose must be one of 0, 1 or 2.")

        if dimensions is None:
            try:
                # use the function's number of arguments as dimensions
                self.num_dimensions = objective_function.__code__.co_argcount
            except TypeError:
                print("Invalid function passed.")
                raise
        else:
            self.num_dimensions = dimensions

        # Assign default boundaries if none passed
        if boundaries is None:
            boundaries = []
            for dimension in range(self.num_dimensions):
                boundaries.append((0, 100))
        else:
            try:
                for dimension in range(len(boundaries), self.num_dimensions):
                    # Default boundaries
                    boundaries.append((0, 100))

                for dimension in range(len(boundaries)):
                    if float(boundaries[dimension][0]) > float(boundaries[dimension][1]):
                            raise ValueError("Incorrect value for boundary - min greater than max for range.")
            except TypeError:
                    raise TypeError("Boundaries not passed correctly.")

        self.points = []
        self.size = population_size
        self.objective_function = objective_function
        self.elite_population_size = int(elite_fraction * self.size)
        self.mutation_probability = mutation_probability
        self.mutation_range = mutation_range
        self.boundaries = boundaries
        self.verbose = verbose
        self.evaluated_fitness_ranks = False
        self.evaluated_diversity_ranks = False
        self.mean_fitness = 0
        self.mean_coordinates = np.zeros((self.num_dimensions, 1))
        self.mean_diversity = 0
        self.num_iterations = 1
        self.multiprocessing = multiprocessing

        # Create points as Point objects
        for pointnumber in range(self.size):
            point = Point(associated_population=self, dimensions=self.num_dimensions)
            self.points.append(point)
            self.points[pointnumber].index = pointnumber

        # If multiprocessing is enabled, create pool of processes.
        if self.multiprocessing:
            if processes is None:
                self.pool = mp.ProcessingPool()
            else:
                self.pool = mp.ProcessingPool(ncpus=processes)

            fitnesses = self.pool.map(lambda coordinates, func: func(*coordinates), [point.coordinates for point in self.points], [self.objective_function] * self.size)

            # Assign fitnesses to each point
            for index, point in enumerate(self.points):
                point.fitness = fitnesses[index]
        else:
            for point in self.points:
                point.evaluate_fitness(self.objective_function)

        # Evaluate fitness and diversity ranks
        self.__evaluate_fitness_ranks()
        self.__evaluate_diversity_ranks()

    # Evaluate the fitness rank of each point in the population
    def __evaluate_fitness_ranks(self):
        if not self.evaluated_fitness_ranks:
            self.mean_fitness = np.sum(point.fitness for point in self.points) / self.size

            # sort and assign ranks
            self.points.sort(key=lambda point: point.fitness, reverse=True)
            for rank_number in range(self.size):
                self.points[rank_number].fitness_rank = rank_number

            self.evaluated_fitness_ranks = True

    # Evaluate the diversity rank of each point in the population
    def __evaluate_diversity_ranks(self):
        if not self.evaluated_diversity_ranks:
            # Find mean coordinates
            self.mean_coordinates = np.sum(point.coordinates for point in self.points) / self.size

            for point in self.points:
                point.diversity = np.sum(np.abs(point.coordinates - self.mean_coordinates))

            self.mean_diversity = np.sum(point.diversity for point in self.points) / self.size

            self.points.sort(key=lambda point: point.diversity, reverse=True)
            for rank_number in range(self.size):
                self.points[rank_number].diversity_rank = rank_number

            self.evaluated_diversity_ranks = True

    # Generate the new population by breeding points
    def __breed(self):
        # Sort according to fitness rank
        self.points.sort(key=lambda point: point.fitness_rank)

        # Push all the really good points first (according to fitness)
        newpopulation = []
        for pointnumber in range(self.elite_population_size):
            newpopulation.append(self.points[pointnumber])

        # Assign weights to being selected for breeding
        weights = [1 / (1 + point.fitness_rank + point.diversity_rank) for point in self.points]

        # Randomly select for the rest and breed
        while len(newpopulation) < self.size:
            parent1 = weighted_choice(list(range(self.size)), weights)
            parent2 = weighted_choice(list(range(self.size)), weights)

            # Don't breed with yourself, dude!
            while parent1 == parent2:
                parent1 = weighted_choice(list(range(self.size)), weights)
                parent2 = weighted_choice(list(range(self.size)), weights)

            # Breed now
            child1, child2 = crossover(self.points[parent1], self.points[parent2])

            # Add the children
            newpopulation.append(child1)
            if len(newpopulation) < self.size:
                newpopulation.append(child2)

        # Re-assign to the new population
        self.points = newpopulation

        # Evaluate fitnesses of new population points
        if self.multiprocessing:
            # Reuse pool of processes
            fitnesses = self.pool.map(lambda coordinates, func: func(*coordinates), [point.coordinates for point in self.points], [self.objective_function] * self.size)

            # Assign fitnesses to each point
            for index, point in enumerate(self.points):
                point.fitness = fitnesses[index]
        else:
            for point in self.points:
                point.evaluate_fitness(self.objective_function)

        self.evaluated_fitness_ranks = False
        self.evaluated_diversity_ranks = False

    # mutate population randomly
    def __mutate(self):
        for point in self.points:
            mutate_probability = uniform(0, 1)
            if mutate_probability < self.mutation_probability:
                point.mutate()
                point.evaluate_fitness(self.objective_function)

                self.evaluated_fitness_ranks = False
                self.evaluated_diversity_ranks = False

    # Perform one iteration of breeding and mutation
    def iterate(self):
        # Breed
        self.__breed()

        # Mutate
        self.__mutate()

        # Find the new population's fitness and diversity ranks
        self.__evaluate_fitness_ranks()
        self.__evaluate_diversity_ranks()

        # Print the population stats, if enabled
        if self.verbose == 1:
            print("Iteration", self.num_iterations, "complete.")
        elif self.verbose == 2:
            print("Iteration", self.num_iterations, "complete, with statistics:")
            print("Mean fitness =", self.mean_fitness)
            print("Mean L1 diversity =", self.mean_diversity)
            print()

        self.num_iterations += 1

    # Perform iterations sequentially
    def converge(self, iterations=15):
        for iteration in range(1, iterations + 1):
            self.iterate()

    # The point with best fitness is the estimate of point of maxima
    def best_estimate(self):
        best_point_fitness = float("-inf")
        best_point = None
        for point in self.points:
            if point.fitness > best_point_fitness:
                best_point_fitness = point.fitness
                best_point = point

        return best_point


# Crossover (breed) 2 points by swapping coordinates
def crossover(point1, point2):
    if point1.associated_population != point2.associated_population:
        raise ValueError("Points are from different populations.")

    child1 = Point(associated_population=point1.associated_population, dimensions=np.size(point1.coordinates))
    child2 = Point(associated_population=point2.associated_population, dimensions=np.size(point2.coordinates))

    splitpoint = randint(1, np.size(point1.coordinates))

    child1.coordinates = np.concatenate([point1.coordinates[:splitpoint], point2.coordinates[splitpoint:]])
    child2.coordinates = np.concatenate([point2.coordinates[:splitpoint], point1.coordinates[splitpoint:]])

    return child1, child2


# Wrapper to build a population and converge to function maxima, returning the best point as a Point object
def maximize(objective_function=None, dimensions=None, population_size=60, boundaries=None, elite_fraction=0.1,
             mutation_probability=0.05, mutation_range=5, verbose=0, multiprocessing=False, processes=None, iterations=15):

    population = Population(objective_function=objective_function, dimensions=dimensions, population_size=population_size,
                            boundaries=boundaries, elite_fraction=elite_fraction, mutation_probability=mutation_probability,
                            mutation_range=mutation_range, verbose=verbose, multiprocessing=multiprocessing, processes=processes)

    population.converge(iterations)
    return population.best_estimate()


# Wrapper to build a population and converge to function minima, returning the best point as a Point object
def minimize(objective_function=None, **kwargs):

    # Negative of objective function
    def objective_function_neg(*args):
        return -objective_function(*args)

    # Minimize the function by maximizing the negative of the function.
    best_point = maximize(objective_function=objective_function_neg, **kwargs)
    best_point.evaluate_fitness(objective_function)

    return best_point


# Helper to unpack arguments with shapes as given
def unpack(args, shapes):
    try:
        # Convert passed arguments to a numpy array
        np_args = np.array(args)
        index = 0
        unpacked_args = []

        # Step through the passed arguments and reshape them one-by-one
        for shape in shapes:
            currprod = 1
            try:
                for val in shape:
                    currprod *= val
            except TypeError:
                currprod *= shape
            finally:
                unpacked_args.append(np_args[index: index + currprod].reshape(shape))
                index += currprod

        if len(shapes) > 1:
            return unpacked_args
        else:
            return unpacked_args[0]

    except (TypeError, IndexError):
        raise

