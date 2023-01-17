import json
import columngenerationsolverpy
import knapsackwithwidth


class Job:
    id = -1
    processing_time = None
    size = None


class Instance:

    def __init__(self, filepath=None):
        self.jobs = []
        self.batch_capacity = 1
        if filepath is not None:
            with open(filepath) as json_file:
                data = json.load(json_file)
                self.batch_capacity = data["batch_capacity"]
                jobs = zip(
                        data["job_processing_times"],
                        data["job_sizes"])
                for (processing_time, size) in jobs:
                    self.add_job(processing_time, size)

    def add_job(self, processing_time, size):
        job = Job()
        job.id = len(self.jobs)
        job.processing_time = processing_time
        job.size = size
        self.jobs.append(job)

    def write(self, filepath):
        data = {"batch_capacity": self.batch_capacity,
                "job_processing_time": [job.processing_time
                                        for job in self.jobs],
                "job_sizes": [job.size for job in self.jobs]}
        with open(filepath, 'w') as json_file:
            json.dump(data, json_file)

    def check(self, filepath):
        print("Checker")
        print("-------")
        with open(filepath) as json_file:
            data = json.load(json_file)
            # Compute makespan.
            makespan = sum(max(self.jobs[job_id].processing_time
                               for job_id in batch)
                           for batch in data["jobs"])
            # Compute number_of_overweighted_batches.
            number_of_overweighted_batches = sum(
                    sum(self.jobs[job_id].size for job_id in batch)
                    > self.batch_capacity
                    for batch in data["jobs"])
            # Compute number_of_scheduled_jobs and number_of_duplicates.
            job_list = [job_id
                        for batch in data["jobs"]
                        for job_id in batch]
            job_set = set(job_list)
            number_of_scheduled_jobs = len(job_set)
            number_of_duplicates = len(job_list) - len(job_set)

            is_feasible = (
                    (number_of_scheduled_jobs == len(self.jobs)) and
                    (number_of_duplicates == 0) and
                    (number_of_overweighted_batches == 0))
            print(f"Makespan: {makespan}")
            print(f"Number of scheduled jobs: {number_of_scheduled_jobs}")
            print(f"Number of duplicates: {number_of_duplicates}")
            print(f"Number of overweighted batches: "
                  f"{number_of_overweighted_batches}")
            print(f"Feasible: {is_feasible}")
            return (is_feasible, makespan)


class PricingSolver:

    def __init__(self, instance):
        self.instance = instance
        self.in_batch = None # (in_batch >> j) & 1 == 1 if object j is in a batch

    def initialize_pricing(self, columns, fixed_columns):
        self.in_batch = 0
        for column_id, column_value in fixed_columns:
            column = columns[column_id]
            if column_value == 1:
                for row_index, row_coefficient in zip(column.row_indices, column.row_coefficients):
                    if row_coefficient == 1:
                        self.in_batch += (1 << row_index)

    def solve_pricing(self, duals):
        # Build subproblem instance.
        sizes = []
        profits = []
        processing_times = []
        real_ids = []

        for job_id, job in enumerate(self.instance.jobs):
            profit = duals[job_id]
            if profit <= 0:
                continue
            if not((self.in_batch >> job_id) & 1):
                profits.append(profit)
                sizes.append(job.size)
                processing_times.append(job.processing_time)
                real_ids.append(job_id)

        # Solve subproblem instance.
        knapsack_instance = knapsackwithwidth.Instance()
        knapsack_instance.capacity = self.instance.batch_capacity
        for i in range(len(sizes)):
            knapsack_instance.add_item(sizes[i], processing_times[i], profits[i])
        
        solution_kp = knapsackwithwidth.dynamic_programming(knapsack_instance)

        # Retrieve column.
        column = columngenerationsolverpy.Column()
        column = columngenerationsolverpy.Column()
        max_proc_time = 0
        for i in solution_kp:
            job_id = real_ids[i]
            column.row_indices.append(job_id)
            column.row_coefficients.append(1)
            max_proc_time = max(max_proc_time, self.instance.jobs[job_id].processing_time)

        column.objective_coefficient = max_proc_time

        return [column]


def get_parameters(instance):
    number_of_constraints = len(instance.jobs)
    p = columngenerationsolverpy.Parameters(number_of_constraints)
    # Objective sense.
    p.objective_sense = "min"
    # Column bounds.
    p.column_lower_bound = 0
    p.column_upper_bound = 1
    # Row bounds.
    for job in instance.jobs:
        p.row_lower_bounds[job.id] = 1
        p.row_upper_bounds[job.id] = 1
        p.row_coefficient_lower_bounds[job.id] = 0
        p.row_coefficient_upper_bounds[job.id] = 1
    # Dummy column objective coefficient.
    p.dummy_column_objective_coefficient = max(job.processing_time for job in instance.jobs) + 1

    # Pricing solver.
    p.pricing_solver = PricingSolver(instance)
    return p


def to_solution(columns, fixed_columns):
    solution = []
    for column, column_value in fixed_columns:
        if column_value == 1:
            s = []
            for index, coef in zip(column.row_indices, column.row_coefficients):
                if coef == 1:
                    s.append(index)
            solution.append(s)
    return solution


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='')
    parser.add_argument(
            "-a", "--algorithm",
            type=str,
            default="greedy",
            help='')
    parser.add_argument(
            "-i", "--instance",
            type=str,
            default="AMOP-Batch-scheduling/data/batchschedulingwithconflictsmakepsan/instance_37.json",
            help='')
    parser.add_argument(
            "-c", "--certificate",
            type=str,
            default="AMOP-Batch-scheduling/certificate.json",
            help='')

    args = parser.parse_args()

    if args.algorithm == "checker":
        instance = Instance(args.instance)
        instance.check(args.certificate)

    elif args.algorithm == "column_generation":
        instance = Instance(args.instance)
        output = columngenerationsolverpy.column_generation(
                get_parameters(instance))

    else:
        instance = Instance(args.instance)
        parameters = get_parameters(instance)
        if args.algorithm == "greedy":
            output = columngenerationsolverpy.greedy(
                    parameters)
        elif args.algorithm == "limited_discrepancy_search":
            output = columngenerationsolverpy.limited_discrepancy_search(
                    parameters, time_limit=60)
        solution = to_solution(parameters.columns, output["solution"])
        if args.certificate is not None:
            data = {"jobs": solution}
            with open(args.certificate, 'w') as json_file:
                json.dump(data, json_file)
            print()
            instance.check(args.certificate)
