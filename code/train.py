from pascalpart import *
import tensorflow as tf
import random, os, pdb
import logictensornetworks as ltn
import config
import time
from evaluate import compute_confusion_matrix_pof, compute_measures, stat, adjust_prec, auc

# swith between GPU and CPU
tf_config = tf.ConfigProto(device_count={'GPU': 1})

# When using semi-supervised training, also load in the pairs for the complete dataset
if config.DO_SEMI_SUPERVISED:
    _, all_pairs_of_train_data, _, _, _, _ = get_data("train", max_rows=1000000000, data_ratio=1)

# loading test data
test_data, pairs_of_test_data, types_of_test_data, partOF_of_pairs_of_test_data, pairs_of_bb_idxs_test, pics = get_data(
    "test", max_rows=50000, data_ratio=1)

print("finished uploading and analyzing data")
print("Start model definition")

# Define the clauses in the knowledge base.
# First we define the facts.
clause_for_types = [ltn.TypeClause(mutExclType,
                                   weight=len(selected_types) * config.WEIGHT_TYPES_EXAMPLES, label='examples_types')]
labels_placeholder = clause_for_types[0].correct_labels

clause_for_positive_examples_of_partOf = [ltn.Clause([ltn.Literal(True, isPartOf, object_pairs_in_partOf)],
                                         label="examples_of_object_pairs_in_partof_relation", weight=config.WEIGHT_PARTOF_EXAMPLES)]

clause_for_negative_examples_of_partOf = [ltn.Clause([ltn.Literal(False, isPartOf, object_pairs_not_in_partOf)],
                                                     label="examples_of_object_pairs_not_in_part_of_relation",
                                                     weight=config.WEIGHT_PARTOF_EXAMPLES)]

# defining axioms from the partOf ontology
parts_of_whole, wholes_of_part = get_part_whole_ontology()

w1 = {}
p1 = {}
pw = {}
oo = ltn.Domain(number_of_features * 2 + 2, label="same_object_pairs")

w0 = ltn.Domain(number_of_features, label="whole_of_part_whole_pair")
p0 = ltn.Domain(number_of_features, label="part_of_part_whole_pair")
p0w0 = ltn.Domain(number_of_features * 2 + 2, label="part_whole_pair")
w0p0 = ltn.Domain(number_of_features * 2 + 2, label="whole_part_pair")

for t in selected_types:
    w1[t] = ltn.Domain(number_of_features, label="whole_predicted_objects_for_" + t)
    p1[t] = ltn.Domain(number_of_features, label="part_predicted_objects_for_" + t)
    pw[t] = ltn.Domain(number_of_features * 2 + 2, label="potential_part_whole_object_pairs_for_" + t)

partOf_is_antisymmetric = [ltn.Clause([ltn.Literal(False, isPartOf, p0w0), ltn.Literal(False, isPartOf, w0p0)],
                                      label="part_of_is_antisymmetric", weight=config.WEIGHT_LOGICAL_CLAUSES)]

partof_is_irreflexive = [ltn.Clause([ltn.Literal(False, isPartOf, oo)],
                                    label="part_of_is_irreflexive", weight=config.WEIGHT_LOGICAL_CLAUSES)]

clauses_for_parts_of_wholes = [ltn.Clause([ltn.Literal(False, isOfType[w], w1[w]),
                                           ltn.Literal(False, isPartOf, pw[w])] + \
                                          [ltn.Literal(True, isOfType[p], p1[w]) for p in parts_of_whole[w]],
                                          label="parts_of_" + w, weight=config.WEIGHT_ONTOLOGY_CLAUSES) for w in parts_of_whole.keys()]

clauses_for_wholes_of_parts = [ltn.Clause([ltn.Literal(False, isOfType[p], p1[p]),
                                           ltn.Literal(False, isPartOf, pw[p])] +
                                          [ltn.Literal(True, isOfType[w], w1[p]) for w in wholes_of_part[p]],
                                          label="wholes_of_" + p, weight=config.WEIGHT_ONTOLOGY_CLAUSES) for p in wholes_of_part.keys()]

# if not config.USE_MUTUAL_EXCL_PREDICATES:
# These are not needed when using the softmax output function. Also speeds up the computation massively
# not to have them :)
o = ltn.Domain(number_of_features, label="a_generi_object")

clauses_for_disjoint_types = [ltn.Clause([ltn.Literal(False, isOfType[t], o),
                                          ltn.Literal(False, isOfType[t1], o)], label=t + "_is_not_" + t1) for t in
                              selected_types for t1 in selected_types if t < t1]

clause_for_at_least_one_type = [
    ltn.Clause([ltn.Literal(True, isOfType[t], o) for t in selected_types],
               label="an_object_has_at_least_one_type")]


# return partof_is_irreflexive + partOf_is_antisymmetric + clauses_for_wholes_of_parts + \
#     clauses_for_parts_of_wholes + clauses_for_disjoint_types + clause_for_at_least_one_type


# TODO: Update this to new data format of types
# def add_noise_to_data(noise_ratio):
#     random.seed(config.RANDOM_SEED)
#     if noise_ratio > 0:
#         freq_other = {}
#
#         for t in selected_types:
#             freq_other[t] = {}
#             number_of_not_t = len(idxs_of_negative_examples_of_types[t])
#             for t1 in selected_types:
#                 if t1 != t:
#                     freq_other[t][t1] = np.float(len(idxs_of_positive_examples_of_types[t1])) / number_of_not_t
#
#         noisy_data_idxs = np.random.choice(range(len(train_data)), int(len(train_data) * noise_ratio), replace=False)
#
#         for idx in noisy_data_idxs:
#             type_of_idx = types_of_train_data[idx]
#             not_types_of_idx = np.setdiff1d(selected_types, type_of_idx)
#             types_of_train_data[idx] = np.random.choice(not_types_of_idx,
#                                                         p=np.array([freq_other[type_of_idx][t1] \
#                                                                     for t1 in not_types_of_idx]))
#
#         noisy_data_pairs_idxs = np.append(np.random.choice(np.where(partOf_of_pairs_of_train_data)[0], int(
#             partOf_of_pairs_of_train_data.sum() * noise_ratio * 0.5)),
#                                           np.random.choice(np.where(np.logical_not(partOf_of_pairs_of_train_data))[0],
#                                                            int(
#                                                                partOf_of_pairs_of_train_data.sum() * noise_ratio * 0.5)))
#
#         for idx in noisy_data_pairs_idxs:
#             partOf_of_pairs_of_train_data[idx] = not (partOf_of_pairs_of_train_data[idx])
#
#     idxs_of_noisy_positive_examples_of_types = {}
#     idxs_of_noisy_negative_examples_of_types = {}
#
#     for type in selected_types:
#         idxs_of_noisy_positive_examples_of_types[type] = np.where(types_of_train_data == type)[0]
#         idxs_of_noisy_negative_examples_of_types[type] = np.where(types_of_train_data != type)[0]
#
#     idxs_of_noisy_positive_examples_of_partOf = np.where(partOf_of_pairs_of_train_data)[0]
#     idxs_of_noisy_negative_examples_of_partOf = np.where(partOf_of_pairs_of_train_data == False)[0]
#
#     print("I have introduced the following errors")
#     for t in selected_types:
#         print("wrong positive", t, len(np.setdiff1d(idxs_of_noisy_positive_examples_of_types[t],
#                                                     idxs_of_positive_examples_of_types[t])))
#         print("wrong negative", t, len(np.setdiff1d(idxs_of_noisy_negative_examples_of_types[t],
#                                                     idxs_of_negative_examples_of_types[t])))
#
#     print("wrong positive partof", len(np.setdiff1d(idxs_of_noisy_positive_examples_of_partOf,
#                                                     idxs_of_positive_examples_of_partOf)))
#     print("wrong negative partof", len(np.setdiff1d(idxs_of_noisy_negative_examples_of_partOf,
#                                                     idxs_of_negative_examples_of_partOf)))
#
#     return idxs_of_noisy_positive_examples_of_types, idxs_of_noisy_negative_examples_of_types, \
#            idxs_of_noisy_positive_examples_of_partOf, idxs_of_noisy_negative_examples_of_partOf


def train_fn(with_facts, with_constraints, iterations, KB, prior_mean, prior_lambda, sess, kb_label):
    random.seed(config.RANDOM_SEED)
    train_writer = tf.summary.FileWriter('logging/' + kb_label + '/train', sess.graph)
    test_writer = tf.summary.FileWriter('logging/' + kb_label + '/test', sess.graph)

    train_kb = True
    for i in range(iterations):
        ti = time.time()
        if i % config.FREQ_OF_FEED_DICT_GENERATION == 0:
            train_kb = True
            feed_dict = get_feed_dict(pairs_of_train_data, with_constraints=with_constraints, with_facts=with_facts)
            feed_dict[KB.prior_mean] = prior_mean
            feed_dict[KB.prior_lambda] = prior_lambda
        if train_kb:
            sat_level, normal_loss, reg_loss = KB.train(sess, feed_dict)
            if np.isnan(sat_level):
                train_kb = False
            if normal_loss < 0:  # Using log-likelihood aggregation
                sat_level = np.exp(-sat_level)
            if sat_level >= config.SATURATION_LIMIT:
                train_kb = False
        if i % config.FREQ_OF_PRINT == 0:
            iter_time = time.time() - ti
            feed_dict = get_feed_dict(pairs_of_train_data)
            for kb in [KB_facts, KB_rules, KB_full, KB_ontology, KB_logical]:
                feed_dict[kb.prior_mean] = prior_mean
                feed_dict[kb.prior_lambda] = prior_lambda

            summary = sess.run(summary_merge, feed_dict)
            train_writer.add_summary(summary, i)

            print(i, 'Sat level', str(sat_level), 'loss', normal_loss, 'regularization', reg_loss, 'iteration time',
                  iter_time)
        if i + 1 % config.FREQ_OF_SAVE == 0:
            KB.save(sess, kb_label)
        if i % config.FREQ_OF_TEST == 0:
            predicted_types_values_tensor = tf.concat([isOfType[t].tensor() for t in selected_types], 1)
            predicted_partOf_value_tensor = ltn.Literal(True, isPartOf, pairs_of_objects).tensor
            # values_of_types = sess.run(predicted_types_values_tensor, {objects.tensor: test_data[:, 1:]})
            # values_of_partOf = sess.run(predicted_partOf_value_tensor, {pairs_of_objects.tensor: pairs_of_test_data})

            feed_dict = {}
            feed_dict[objects.tensor] = test_data[:, 1:]
            feed_dict[pairs_of_objects.tensor] = pairs_of_test_data

            feed_dict_rules(feed_dict, pairs_of_test_data[np.random.choice(range(pairs_of_test_data.shape[0]),
                                                                           config.NUMBER_PAIRS_AXIOMS_TESTING)], )

            values_of_types, values_of_partOf, summary_r = sess.run([predicted_types_values_tensor,
                                                                     predicted_partOf_value_tensor,
                                                                     rules_summary], feed_dict)

            cm = compute_confusion_matrix_pof(config.THRESHOLDS, values_of_partOf,
                                              pairs_of_test_data, partOF_of_pairs_of_test_data)
            measures = {}
            compute_measures(cm, 'test', measures)
            precision, recall = stat(measures, 'test')
            precision = adjust_prec(precision)
            auc_pof = auc(precision, recall)

            max_type_labels = np.argmax(values_of_types, 1)
            max_type_labels = selected_types[max_type_labels]
            correct = np.where(max_type_labels == types_of_test_data)[0]
            prec_types = len(correct) / len(max_type_labels)
            summary_t = tf.Summary(value=[
                tf.Summary.Value(tag="auc_pof", simple_value=auc_pof),
                tf.Summary.Value(tag="prec_types", simple_value=prec_types)
            ])

            test_writer.add_summary(summary_r, i)
            test_writer.add_summary(summary_t, i)

    train_writer.flush()
    test_writer.flush()

    return feed_dict, auc_pof, prec_types


def train(KB, seed, alg='nc', noise_ratio=0.0, data_ratio=config.RATIO_DATA[0],
          lambda_2=config.LAMBDA_2, prior_mean=None):
    prior_lambda = config.REGULARIZATION

    alg_label = ("_SEMI_" if config.DO_SEMI_SUPERVISED else "") + "_nr_" + str(noise_ratio) + "_dr_" + str(data_ratio) \
                + config.DATASET + 'TNORM' + config.TNORM + 'FORALL' + config.FORALL_AGGREGATOR + \
                'CLAUSE' + config.CLAUSE_AGGREGATOR + '_' + config.EXPERIMENT_NAME + '_SEED_' + str(seed)

    # defining the label of the background knowledge
    kb_label = "KB_" + alg + alg_label

    if alg == 'prior':
        kb_label = "KB_" + alg + '_l2_' + str(lambda_2) + alg_label
        prior_lambda = lambda_2

    with tf.Session(config=tf_config) as sess:
        sess.run(tf.global_variables_initializer())
        # start training
        if prior_mean is None:
            prior_mean = np.zeros(sess.run(KB.num_params, {}))
        else:
            saver = tf.train.Saver()
            saver.restore(sess, 'models/prior.ckpt')

        _, auc_pof, prec_types = train_fn(with_facts=True, with_constraints=alg in ['wc', 'wconto', 'wclogic'],
              iterations=config.MAX_TRAINING_ITERATIONS, KB=KB, prior_mean=prior_mean, prior_lambda=prior_lambda,
                 sess=sess, kb_label=kb_label)

        KB.save(sess, kb_label)
        print("end of training")
    return auc_pof, prec_types


def feed_dict_rules(feed_dict, pairs_data, with_constraints=True):
    # feed data for axioms
    tmp = pairs_data
    # if not config.USE_MUTUAL_EXCL_PREDICATES:
    feed_dict[o.tensor] = tmp[:, :number_of_features]

    if with_constraints:
        for t in selected_types:
            feed_dict[pw[t].tensor] = tmp
            feed_dict[w1[t].tensor] = tmp[:, number_of_features:2 * number_of_features]
            feed_dict[p1[t].tensor] = tmp[:, :number_of_features]

        feed_dict[oo.tensor] = np.concatenate([tmp[:, :number_of_features], tmp[:, :number_of_features],
                                               np.ones((tmp.shape[0], 2), dtype=float)], axis=1)
        feed_dict[p0w0.tensor] = tmp
        feed_dict[w0.tensor] = feed_dict[p0w0.tensor][:, number_of_features:2 * number_of_features]
        feed_dict[p0.tensor] = feed_dict[p0w0.tensor][:, :number_of_features]
        feed_dict[w0p0.tensor] = np.concatenate([
            feed_dict[w0.tensor], feed_dict[p0.tensor], feed_dict[p0w0.tensor][:, -1:-3:-1]], axis=1)
    return feed_dict


def get_feed_dict(pairs_data, with_constraints=True, with_facts=True):
    feed_dict = {}

    if with_facts:
        chosen_examples = np.random.choice(np.size(train_data, 0), config.N_EXAMPLES_TYPES)
        feed_dict[objects.tensor] = train_data[chosen_examples][:, 1:]
        feed_dict[labels_placeholder] = [labelOfType[t] for t in types_of_train_data[chosen_examples]]

        # positive and negative examples for partOF
        feed_dict[object_pairs_in_partOf.tensor] = \
            pairs_of_train_data[np.random.choice(idxs_of_positive_examples_of_partOf, config.N_POS_EXAMPLES_PARTOF)]

        feed_dict[object_pairs_not_in_partOf.tensor] = \
            pairs_of_train_data[np.random.choice(idxs_of_negative_examples_of_partOf, config.N_NEG_EXAMPLES_PARTOF)]
    if config.DO_SEMI_SUPERVISED:
        feed_dict_rules(feed_dict,
                        all_pairs_of_train_data[np.random.choice(range(all_pairs_of_train_data.shape[0]),
                                                                 config.number_of_pairs_for_axioms)], with_constraints)
    else:
        feed_dict_rules(feed_dict,
                        pairs_data[np.random.choice(range(pairs_data.shape[0]), config.number_of_pairs_for_axioms)],
                        with_constraints)
    return feed_dict


# defining the clauses of the background knowledge
facts = clause_for_types + clause_for_positive_examples_of_partOf + clause_for_negative_examples_of_partOf

rules_ontology = clauses_for_wholes_of_parts + clauses_for_parts_of_wholes
rules_logical = partof_is_irreflexive + partOf_is_antisymmetric
rules = rules_ontology + rules_logical

if not config.USE_MUTUAL_EXCL_PREDICATES:
    rules += clauses_for_disjoint_types + clause_for_at_least_one_type

for rule in rules:
    tensor = rule.tensor
    tf.summary.scalar('rules/' + rule.label, tensor, collections=['rules'])

# for fact in facts:
#     tensor = fact.tensor
#     tf.summary.scalar('facts/' + fact.label, tensor, collections=['rules'])

clause_to_debug = clauses_for_parts_of_wholes[0]
for literal in clause_to_debug.literals:
    tensor = tf.reshape(tf.reduce_mean(literal.tensor), ())
    tf.summary.scalar('rules/' + clause_to_debug.label + '/' + literal.predicate.label + '_' +
                      literal.domain.label + str(literal.polarity), tensor, collections=['rules'])

clause_to_debug = clauses_for_parts_of_wholes[1]
for literal in clause_to_debug.literals:
    tensor = tf.reshape(tf.reduce_mean(literal.tensor), ())
    tf.summary.scalar('rules/' + clause_to_debug.label + '/' + literal.predicate.label + '_' +
                      literal.domain.label + str(literal.polarity), tensor, collections=['rules'])


# Lists all predicates
predicates = list(isOfType.values()) + [isPartOf]
mutExPredicates = [mutExclType] if config.USE_MUTUAL_EXCL_PREDICATES else []

# Create the different knowledge bases.
print('Defining knowledge bases')
KB_full = ltn.KnowledgeBase(predicates, mutExPredicates, facts + rules, "full", "models/")
KB_facts = ltn.KnowledgeBase(predicates, mutExPredicates, facts, "facts", "models/")
KB_rules = ltn.KnowledgeBase(predicates, mutExPredicates, rules, "rules", "models/")

KB_ontology = ltn.KnowledgeBase(predicates, mutExPredicates, facts + rules_ontology, "ontology", "models/")
KB_logical = ltn.KnowledgeBase(predicates, mutExPredicates, facts + rules_logical, "logical", "models/")

# The summary contains the loss tensors for the three Knowledge Bases defined up here.
summary_merge = tf.summary.merge_all(key='train')
rules_summary = tf.summary.merge_all(key='rules')

for nr in config.NOISE_VALUES:
    results = []
    for eval in range(config.AMOUNT_OF_EVALUATIONS):
        results.append([])
        print('Starting eval', eval)

        seed = config.RANDOM_SEED + eval

        # Loading training data
        train_data, pairs_of_train_data, types_of_train_data, \
        partOf_of_pairs_of_train_data, _, _ = get_data("train", max_rows=1000000000, seed=seed)

        # computing positive and negative examples for types and partof
        idxs_of_positive_examples_of_partOf = np.where(partOf_of_pairs_of_train_data)[0]
        idxs_of_negative_examples_of_partOf = np.where(partOf_of_pairs_of_train_data == False)[0]

        # Compute the prior mean for the current dataset
        if 'prior' in config.ALGORITHMS:
            with tf.Session(config=tf_config) as sess:
                sess.run(tf.global_variables_initializer())
                prior_mean = np.zeros(sess.run(KB_rules.num_params, {}))

                feed_dict, _, _ = train_fn(with_facts=False, with_constraints=True, iterations=config.MAX_PRIOR_TRAINING_IT,
                                           KB=KB_rules, prior_mean=prior_mean, prior_lambda=config.REGULARIZATION,
                                           sess=sess, kb_label='prior_training')

                KB_rules.save(sess, 'prior')

                # Create the parameters for the informative prior
                prior_mean = sess.run(KB_rules.omega, feed_dict)

        for alg in config.ALGORITHMS:
            lambda_2s = config.LAMBDA_2_VALUES if alg == 'prior' else [config.LAMBDA_2]
            for lambda_2 in lambda_2s:
                if alg == 'wconto':
                    auc_pof, prec_types = train(KB_ontology, seed, alg=alg, noise_ratio=nr, prior_mean=None)
                elif alg == 'wclogic':
                    auc_pof, prec_types = train(KB_logical, seed, alg=alg, noise_ratio=nr, prior_mean=None)
                else:
                    auc_pof, prec_types = train(KB_full if alg == 'wc' else KB_facts, seed, alg=alg, noise_ratio=nr,
                                                lambda_2=lambda_2, prior_mean=prior_mean if alg == 'prior' else None)
                print('EVAL FINISHED')
                print('eval', eval, 'AUC POF', auc_pof, 'prec types', prec_types)
                results[eval].append(auc_pof)
                results[eval].append(prec_types)
    print('FINISHED THE COMPLETE RUN')
    print('Results:')
    for i in range(config.AMOUNT_OF_EVALUATIONS):
        print('Evaluation', i, ':', results[i])
    with open('results.csv', 'w') as csvfile:
        csvfile.write(','.join([alg + 'auc_pof,' + alg + 'prec_types' for alg in config.ALGORITHMS]))
        for i in range(config.AMOUNT_OF_EVALUATIONS):
            csvfile.write(','.join([str(r) for r in results[i]]))
