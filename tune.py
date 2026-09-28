# genetic algorithm for the evaluation weights
#
# each generation every pair of genomes plays the same few random openings
# twice (colors swapped) at a fixed search depth; a genome's fitness is its
# total score (win 1, draw 0.5). the best few survive unchanged and the rest
# of the next generation is bred from tournament-selected parents by blending
# in log space (weights are scale-like, so ratios are what matter) and
# applying multiplicative gaussian mutation.
import argparse
import json
import math
import random
import time
from multiprocessing import Pool

from eval import DEFAULT_WEIGHTS, WEIGHT_NAMES
from minimax import Engine
from play import engine_player, play_game, random_opening


def play_one(args):
    black_w, white_w, opening, depth = args
    black = engine_player(Engine(weights=black_w), time_limit=1e9, max_depth=depth)
    white = engine_player(Engine(weights=white_w), time_limit=1e9, max_depth=depth)
    result, _ = play_game(black, white, opening)
    return {"black wins": 1.0, "white wins": 0.0, "draw": 0.5}[result]


def round_robin(pool, population, openings, depth):
    jobs, owners = [], []
    for a in range(len(population)):
        for b in range(a + 1, len(population)):
            for opening in openings:
                jobs.append((population[a], population[b], opening, depth))
                owners.append((a, b))
                jobs.append((population[b], population[a], opening, depth))
                owners.append((b, a))
    fitness = [0.0] * len(population)
    for (black, white), score in zip(owners, pool.map(play_one, jobs, chunksize=4)):
        fitness[black] += score
        fitness[white] += 1.0 - score
    return fitness


def mutate(rng, genome, sigma):
    return [max(1, round(w * math.exp(rng.gauss(0, sigma)))) for w in genome]


def crossover(rng, a, b):
    child = []
    for x, y in zip(a, b):
        t = rng.random()
        child.append(round(math.exp(t * math.log(x) + (1 - t) * math.log(y))))
    return child


def tournament(rng, population, fitness, k=3):
    picks = rng.sample(range(len(population)), k)
    return population[max(picks, key=lambda i: fitness[i])]


def evolve(generations, size, elites, openings_per_gen, depth, sigma, seed, out, workers):
    rng = random.Random(seed)
    population = [list(DEFAULT_WEIGHTS)] + [mutate(rng, DEFAULT_WEIGHTS, 0.4) for _ in range(size - 1)]
    history = []
    with Pool(workers) as pool:
        for gen in range(generations):
            start = time.time()
            openings = [random_opening(rng, 3) for _ in range(openings_per_gen)]
            fitness = round_robin(pool, population, openings, depth)
            order = sorted(range(size), key=lambda i: -fitness[i])
            games = 2 * openings_per_gen * (size - 1)
            best = population[order[0]]
            history.append({"generation": gen, "best": best, "best_score": fitness[order[0]] / games,
                            "mean_score": sum(fitness) / size / games})
            print(f"gen {gen:3d}  best {fitness[order[0]] / games:.3f}  "
                  f"({time.time() - start:.0f}s)  {best}", flush=True)
            with open(out, "w") as f:
                json.dump({"names": WEIGHT_NAMES, "best": best, "history": history}, f, indent=1)
            survivors = [population[i] for i in order[:elites]]
            children = []
            while len(children) < size - elites:
                a = tournament(rng, population, fitness)
                b = tournament(rng, population, fitness)
                children.append(mutate(rng, crossover(rng, a, b), sigma))
            population = survivors + children
    return best


def main():
    parser = argparse.ArgumentParser(description="tune evaluation weights with a genetic algorithm")
    parser.add_argument("--generations", type=int, default=30)
    parser.add_argument("--size", type=int, default=16)
    parser.add_argument("--elites", type=int, default=4)
    parser.add_argument("--openings", type=int, default=2, help="openings per pairing per generation")
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--sigma", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--out", default="tuned_weights.json")
    args = parser.parse_args()
    evolve(args.generations, args.size, args.elites, args.openings, args.depth,
           args.sigma, args.seed, args.out, args.workers)


if __name__ == "__main__":
    main()
