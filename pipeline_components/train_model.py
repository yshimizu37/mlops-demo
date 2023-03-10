from kfp.components import OutputPath

"""
Reference:
https://www.tensorflow.org/hub/tutorials/tf2_image_retraining
"""

def transfer_learning(
    model_name:str,
    data_dir:str,
    batch_size:int,
    epochs:int,
    learning_rate:float,
    momentum:float,
    label_smoothing:float,
    dropout_rate:float,
    output_model_path:OutputPath('model'),
    output_history_path:OutputPath('history'),
    ):
    import itertools
    import os
    import numpy as np
    import json
    import tensorflow as tf
    import tensorflow_hub as hub
    print("TF version:", tf.__version__)
    print("Hub version:", hub.__version__)
    print("GPU is", "available" if tf.config.list_physical_devices('GPU') else "NOT AVAILABLE")

    # base model definition
    # MODEL_NAME = "efficientnetv2-xl-21k"
    MODEL_URL = "https://tfhub.dev/google/imagenet/inception_v3/feature_vector/5"
    IMAGE_SIZE = (299, 299)
    # DATASET_ROOT = os.path.join(data_dir, "flower_photos")
    DATASET_ROOT = data_dir

    # preprocessing dataset
    # train_ds = build_dataset("training")
    train_ds = tf.keras.preprocessing.image_dataset_from_directory(
      DATASET_ROOT,
      validation_split=.20,
      subset="training",
      label_mode="categorical",
      seed=123,
      image_size=IMAGE_SIZE,
      batch_size=1)
    class_names = tuple(train_ds.class_names)
    train_size = train_ds.cardinality().numpy()
    train_ds = train_ds.unbatch().batch(batch_size)
    train_ds = train_ds.repeat()

    # normalization_layer = tf.keras.layers.Rescaling(1. / 255)
    normalization_layer = tf.keras.layers.experimental.preprocessing.Rescaling(1. / 255)
    preprocessing_model = tf.keras.Sequential([normalization_layer])
    train_ds = train_ds.map(lambda images, labels:
                            (preprocessing_model(images), labels))

    # val_ds = build_dataset("validation")
    val_ds = tf.keras.preprocessing.image_dataset_from_directory(
      DATASET_ROOT,
      validation_split=.20,
      subset="validation",
      label_mode="categorical",
      seed=123,
      image_size=IMAGE_SIZE,
      batch_size=1)
    valid_size = val_ds.cardinality().numpy()
    val_ds = val_ds.unbatch().batch(batch_size)
    val_ds = val_ds.map(lambda images, labels:
                        (normalization_layer(images), labels))

    # define model
    print("Building model with", MODEL_URL)
    model = tf.keras.Sequential([
        # Explicitly define the input shape so the model can be properly
        # loaded by the TFLiteConverter
        tf.keras.layers.InputLayer(input_shape=IMAGE_SIZE + (3,)),
        hub.KerasLayer(MODEL_URL, trainable=False),
        tf.keras.layers.Dense(len(class_names), activation='softmax')
    ])
    model.build((None,)+IMAGE_SIZE+(3,))
    model.summary()

    model.compile(
        optimizer=tf.keras.optimizers.SGD(learning_rate=learning_rate, momentum=momentum), 
        loss=tf.keras.losses.CategoricalCrossentropy(from_logits=True, label_smoothing=label_smoothing),
        metrics=['accuracy']
        )
    
    # train model (transfer learning)
    steps_per_epoch = train_size // batch_size
    validation_steps = valid_size // batch_size
    hist = model.fit(
        train_ds,
        epochs=epochs, steps_per_epoch=steps_per_epoch,
        validation_data=val_ds,
        validation_steps=validation_steps).history
    
    # save history
    print(hist)
    with open(output_history_path, mode='w') as f:
      f.write(json.dumps(hist))

    # saved_model_path = f"/tmp/saved_flowers_model_{model_name}"
    tf.saved_model.save(model, output_model_path)