"""
@title
@description
"""
import os
import random

import cv2 as cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# have to set env variable before importing tensorflow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from tensorflow import keras
from tqdm import tqdm

from SystemControl import DATA_DIR
from SystemControl.DataSource.PhysioDataSource import SUBJECT_NAMES, PhysioDataSource
from SystemControl.DataTransformer import Interpolation
from SystemControl.utilities import find_files_by_type, filter_list_of_dicts

"""
0 = all messages are logged (default behavior)
1 = INFO messages are not printed
2 = INFO and WARNING messages are not printed
3 = INFO, WARNING, and ERROR messages are not printed
"""


def show_sample(img_sample, target_label):
    plt.figure()
    plt.imshow(img_sample)
    plt.tick_params(
        axis='both', which='both',
        bottom=False, top=False, labelbottom=False,
        right=False, left=False, labelleft=False
    )
    plt.xlabel(target_label)
    plt.grid(False)
    plt.show()
    plt.close()
    return


def show_top_samples(sample_imgs, sample_labels, title: str, num_rows: int = 5, num_cols: int = 5):
    fig, ax_list = plt.subplots(num_rows, num_cols, figsize=(num_cols, num_rows))
    fig.suptitle(f'{title} images: top {num_rows * num_cols}')
    for each_ax_idx, each_ax in enumerate(ax_list.flat):
        each_ax.set_xticks([])
        each_ax.set_yticks([])
        each_ax.imshow(sample_imgs[each_ax_idx])
        each_ax.set_xlabel(sample_labels[each_ax_idx])
    plt.show()
    plt.close()
    return


def plot_confusion_matrix(y_true, y_pred, class_labels, title, cmap='Blues', annotate_entries=True):
    title = f'Target: \'{title}\''
    conf_mat = confusion_matrix(y_true, y_pred)
    conf_mat = conf_mat.astype('float') / conf_mat.sum(axis=1)[:, np.newaxis]

    lower_bound = np.min(y_true) - 0.5
    upper_bound = np.max(y_true) + 0.5

    fig, ax = plt.subplots()
    im = ax.imshow(conf_mat, interpolation='nearest', cmap=cmap)
    ax.figure.colorbar(im, ax=ax)

    xtick_marks = np.arange(conf_mat.shape[1])
    ytick_marks = np.arange(conf_mat.shape[0])

    ax.set_xticks(xtick_marks)
    ax.set_yticks(ytick_marks)

    ax.set_xbound(lower=lower_bound, upper=upper_bound)
    ax.set_ybound(lower=lower_bound, upper=upper_bound)
    ax.invert_yaxis()

    ax.set_xticklabels(class_labels)
    ax.set_yticklabels(class_labels)

    ax.set_xlabel('Predicted label')
    ax.set_ylabel('True label')

    ax.set_title(title)
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right', rotation_mode='anchor')

    if annotate_entries:
        annot_format = '0.2f'
        thresh = conf_mat.max() / 2.
        for i in range(conf_mat.shape[0]):
            for j in range(conf_mat.shape[1]):
                conf_entry = conf_mat[i, j]
                ax.text(
                    j, i, format(conf_entry, annot_format), ha='center', va='center',
                    color='white' if conf_entry > thresh else 'black'
                )
    fig.tight_layout()

    plt.show()
    plt.close()
    return


def plot_history_metric(model_histroy, metric_name):
    upper_y = np.max((model_histroy.history[metric_name], model_histroy.history['val_accuracy'])) * 1.2
    plt.plot(model_histroy.epoch, model_histroy.history[metric_name], label=metric_name)
    plt.plot(model_histroy.epoch, model_histroy.history[f'val_{metric_name}'], label=f'validation {metric_name}')
    plt.xlabel('Epoch')
    plt.ylabel(metric_name)
    plt.ylim([0, upper_y])
    plt.xlim([model_histroy.epoch[0] - 0.5, model_histroy.epoch[-1] + 0.5])
    plt.legend(loc='lower right')
    plt.show()
    plt.close()
    return


class TfClassifier:

    def __init__(self, base_data_directory):
        self._data_directory = base_data_directory
        self._data = []

        self.__load_images()

        # input_shape, num_classes
        # self.model = self.build_cnn_v0()
        return

    def __load_images(self):
        img_files = find_files_by_type('png', self._data_directory)
        for each_file in img_files:
            file_parts = each_file.split(os.path.sep)
            file_id, file_ext = os.path.splitext(file_parts[-1])
            event_type = file_parts[-2]
            file_subject = file_parts[-3]
            file_interp = file_parts[-4]
            file_source = file_parts[-5]
            data_entry = {'event': event_type, 'subject': file_subject, 'interpolation': file_interp,
                          'source': file_source, 'id': file_id, 'path': each_file}
            self._data.append(data_entry)
        return

    @staticmethod
    def __build_cnn_v0(input_shape=None, num_classes=None):
        model = keras.Sequential()

        # base architecture
        model.add(keras.layers.Conv2D(32, (3, 3), activation='relu', input_shape=input_shape))
        model.add(keras.layers.MaxPooling2D((2, 2)))
        model.add(keras.layers.Conv2D(64, (3, 3), activation='relu'))
        model.add(keras.layers.MaxPooling2D((2, 2)))
        model.add(keras.layers.Conv2D(64, (3, 3), activation='relu'))

        # dense layers
        model.add(keras.layers.Flatten())
        model.add(keras.layers.Dense(64, activation='relu'))
        model.add(keras.layers.Dense(num_classes, activation='softmax'))
        return model


def main():
    #############################################
    print(f'TensorFlow version: {tf.__version__}')
    print(f'Eager execution: {tf.executing_eagerly()}')
    #############################################
    heatmap_dir = os.path.join(DATA_DIR, 'heatmaps')
    tf_classifier = TfClassifier(heatmap_dir)
    
    #############################################
    display_ds_analytics = False
    display_samples = False
    display_metrics = False
    save_model = False
    display_model = True
    train_verbosity = 1

    target_column = 'event'
    num_subjects = 1
    num_epochs = 1
    b_size = 1
    lr = 1e-4
    img_height = 224
    img_width = 224

    img_dims = (img_width, img_height)
    optimizer = keras.optimizers.Adam(lr=lr)
    loss_func = keras.losses.SparseCategoricalCrossentropy()
    fit_callbacks = [
        keras.callbacks.EarlyStopping(
            monitor='val_accuracy', verbose=1, patience=3, mode='max', restore_best_weights=True
        )
    ]
    metrics_list = [
        keras.metrics.SparseCategoricalAccuracy(name='accuracy'),
        keras.metrics.CosineSimilarity(name='cos_similarity'),
        keras.metrics.CategoricalHinge(name='categorical_hinge'),
        keras.metrics.MeanAbsoluteError(name='mae'),
        keras.metrics.MeanSquaredError(name='mse'),
    ]

    train_size, test_size, val_size = (0.6, 0.15, 0.25)
    rand_seed = 42

    rand_generator = random.Random(rand_seed)
    chosen_beings = sorted(rand_generator.sample(SUBJECT_NAMES, k=num_subjects))

    source_list = [PhysioDataSource.NAME]
    interpolation_list = [
        Interpolation.LINEAR.name,
        Interpolation.QUADRATIC.name,
        Interpolation.CUBIC.name
    ]

    filtered_dataset = filter_list_of_dicts(
        heatmap_dataset,
        {'subject': chosen_beings, 'interpolation': interpolation_list, 'source': source_list}
    )
    rand_generator = random.Random(rand_seed)
    rand_generator.shuffle(filtered_dataset)
    filtered_df = pd.DataFrame(filtered_dataset)
    class_names = sorted(filtered_df[target_column].unique())
    target_str_to_idx = {
        class_name: class_idx
        for class_idx, class_name in enumerate(class_names)
    }
    filtered_df.replace(target_str_to_idx, inplace=True)

    train_val_df, test_filtered_df = train_test_split(
        filtered_df, test_size=test_size, random_state=rand_seed
    )
    train_filtered_df, val_filtered_df = train_test_split(
        train_val_df, test_size=test_size, random_state=rand_seed
    )
    #############################################
    train_paths_df, train_targets_df = train_filtered_df['path'], train_filtered_df[target_column]
    val_paths_df, val_targets_df = val_filtered_df['path'], val_filtered_df[target_column]
    test_paths_df, test_targets_df = test_filtered_df['path'], test_filtered_df[target_column]
    #############################################
    train_images = []
    for each_path in tqdm(train_paths_df, desc=f'Loading train images'):
        img = cv2.imread(each_path)
        img = cv2.resize(img, img_dims)
        train_images.append(img)
    train_images = np.asarray(train_images)

    val_images = []
    for each_path in tqdm(val_paths_df, desc=f'Loading validation images'):
        img = cv2.imread(each_path)
        img = cv2.resize(img, img_dims)
        val_images.append(img)
    val_images = np.asarray(val_images)

    test_images = []
    for each_path in tqdm(test_paths_df, desc=f'Loading test images'):
        img = cv2.imread(each_path)
        img = cv2.resize(img, img_dims)
        test_images.append(img)
    test_images = np.asarray(test_images)
    #############################################
    train_labels = train_targets_df.to_numpy()
    val_labels = val_targets_df.to_numpy()
    test_labels = test_targets_df.to_numpy()

    train_images = train_images / 255.0
    val_images = val_images / 255.0
    test_images = test_images / 255.0

    train_img_shape = train_images.shape
    val_img_shape = val_images.shape
    test_img_shape = test_images.shape

    train_event_counts = train_filtered_df[target_column].value_counts()
    val_event_counts = val_filtered_df[target_column].value_counts()
    test_event_counts = test_filtered_df[target_column].value_counts()

    if display_ds_analytics:
        print('=====================================================================')
        print(f'Data source: {", ".join(source_list)}')
        print(f'Number of interpolation types: {len(interpolation_list)}')
        print(f'\t{", ".join(interpolation_list)}')
        print(f'Number of chosen beings: {len(chosen_beings)}')
        print(f'\t{", ".join(chosen_beings)}')
        print(f'Number of classes: {len(class_names)}')
        print(f'\t{", ".join(class_names)}')
        print(f'Number of entries in filtered dataset: {len(filtered_dataset)}')
        print('=====================================================================')
        print(f'Number train images: {len(train_images)} -> {len(train_labels)}')
        sep = '\t'
        for event_idx, event_count in train_event_counts.iteritems():
            print(f'{sep}{class_names[event_idx]}: {event_count} '
                  f'({(event_count * 100) / len(train_labels):0.4f} %)', end='')
            sep = ', '
        print()
        print('=====================================================================')
        print(f'Number validation images: {len(val_images)} -> {len(val_labels)}')
        sep = '\t'
        for event_idx, event_count in val_event_counts.iteritems():
            print(f'{sep}{class_names[event_idx]}: {event_count} '
                  f'({(event_count * 100) / len(val_labels):0.4f} %)', end='')
            sep = ', '
        print()
        print('=====================================================================')
        print(f'Number test images: {len(test_images)} -> {len(test_labels)}')
        sep = '\t'
        for event_idx, event_count in test_event_counts.iteritems():
            print(f'{sep}{class_names[event_idx]}: {event_count} '
                  f'({(event_count * 100) / len(test_labels):0.4f} %)', end='')
            sep = ', '
        print()
        print('=====================================================================')
        print(f'Shape train images: {train_img_shape}')
        print(f'Shape validation images: {val_img_shape}')
        print(f'Shape test images: {test_img_shape}')
        print('=====================================================================')

    if display_samples:
        show_top_samples(train_images, train_labels, title='Train', num_rows=5, num_cols=5)
        show_top_samples(val_images, val_labels, title='Validation', num_rows=5, num_cols=5)
        show_top_samples(test_images, test_labels, title='Test', num_rows=5, num_cols=5)

    #############################################
    model = build_cnn_v0(input_shape=train_img_shape[1:], num_classes=len(class_names))

    model.compile(
        optimizer=optimizer,
        loss=loss_func,
        metrics=metrics_list
    )

    train_history = model.fit(train_images, train_labels,
                              epochs=num_epochs, verbose=train_verbosity, batch_size=b_size,
                              callbacks=fit_callbacks, validation_data=(val_images, val_labels))

    eval_metrics = model.evaluate(test_images, test_labels, verbose=0)
    ##########################################################################
    if display_metrics:
        print('==========================================================================')
        print(f'Test loss: {eval_metrics[0]}', end='')
        sep = '\n\t'
        # loss is the first value in 'eval_metrics' -> skip over it
        eval_metrics = eval_metrics[1:]
        for metric_index, each_metric in enumerate(metrics_list):
            print(f'{sep}{each_metric.name}: {eval_metrics[metric_index]:0.4f}', end='')
            sep = ', '
        print()
        print('==========================================================================')
        test_predictions = model.predict(test_images, batch_size=b_size)
        top_test_preds = [np.argmax(each_pred) for each_pred in test_predictions]
        plot_confusion_matrix(
            y_pred=top_test_preds, y_true=test_labels, class_labels=class_names,
            title=target_column, annotate_entries=False
        )
        plot_history_metric(train_history, 'accuracy')
        plot_history_metric(train_history, 'loss')
        print('==========================================================================')

    output_dir = os.path.join(DATA_DIR, 'output', 'tf')
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    model_name = f''
    if display_model:
        print('==========================================================================')
        model.summary()
        # pip install pydot
        # pip install pydotplus
        # pip install graphviz
        #   https://www.graphviz.org/download/
        #   Make sure that the directory containing the dot executable is on your system's path
        keras.utils.plot_model(model, os.path.join(output_dir, f'{model_name}_plot.png'), show_shapes=True)
        print('==========================================================================')
    if save_model:
        with open(os.path.join(output_dir, f'{model_name}_metrics.txt'), 'a+') as metric_file:
            # print(f'Test loss: {eval_metrics[0]}', end='')
            # sep = '\n\t'
            # # loss is the first value in 'eval_metrics' -> skip over it
            # eval_metrics = eval_metrics[1:]
            # for metric_index, each_metric in enumerate(metrics_list):
            #     print(f'{sep}{each_metric.name}: {eval_metrics[metric_index]:0.4f}', end='')
            #     sep = ', '
            # print()
            # metric_file.write(f'{each_subject}: {test_acc:0.2f}')
            #
            # eval_metrics as dict
            # add model weights
            # add run params (subject, interp, etc)
            # write json to file
            pass
    return


if __name__ == '__main__':
    main()
