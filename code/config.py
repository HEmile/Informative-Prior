# TRAINING
MAX_TRAINING_ITERATIONS = 500

MAX_PRIOR_TRAINING_IT = 150

FREQ_OF_FEED_DICT_GENERATION = 1

FREQ_OF_SAVE = 1000

FREQ_OF_PRINT = 20

SATURATION_LIMIT = 0.95

NOISE_VALUES = [0., 0.1, 0.2, 0.3, 0.4]

LAMBDA_2_VALUES = [1e-2, 1e-1]

N_POS_EXAMPLES_TYPES = 250
N_NEG_EXAMPLES_TYPES = 250
N_POS_EXAMPLES_PARTOF = 250
N_NEG_EXAMPLES_PARTOF = 250
number_of_pairs_for_axioms = 1000

RATIO_DATA = 0.25

# Options: 'all', 'indoor', 'vehicle', 'animal'
DATASET = 'indoor'

# List. Return [True, False] to create models for both training with and without constraints.
# ALGORITHMS = ['prior']
ALGORITHMS = ['prior']
# ALGORITHMS = ['nc', 'wc']

EVAL_ALGORITHMS = ['prior_l2_0.01', 'prior_l2_0.001',  'prior_l2_0.0001','prior_l2_1e-05']
# EVAL_ALGORITHMS = ['prior_l2_0.001', 'prior_l2_1e-05', 'wc', 'nc']

# LOGIC TENSOR NETWORK SETUP
DEFAULT_LAYERS = 2

TYPE_LAYERS = 5

PART_OF_LAYERS = 2

REGULARIZATION = 1e-6

LAMBDA_2 = 1e-7

TNORM = "product"

FORALL_AGGREGATOR = "product"

POSITIVE_FACT_PENALTY = 0.

CLAUSE_AGGREGATOR = "log-likelihood"

OPTIMIZER = 'rmsprop'