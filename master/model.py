import tensorflow as tf
import tensorflow.keras as keras

kl = keras.layers
ka = keras.activations
kr = keras.regularizers

# pre-definiamo un paio di sequenze di blocchi comuni nel modello
def B_R(input):
    step1 = kl.BatchNormalization()(input)
    step2 = kl.ReLU()(step1)
    return step2
def B_R_A(input):
    step2 = B_R(input)
    step3 = kl.AveragePooling2D(pool_size=(2,2), strides=(2,2))(step2)
    return step3

# definiamo lo squeeze-and-excitation block
def SE_block(input, squeeze_factor=2):
    # recuperiamo il numero di canali
    channels = input.get_shape()[-1]
    # squeeze
    sqz = kl.GlobalAveragePooling2D()(input)
    # excitation
    exc_step1 = kl.Dense(channels//squeeze_factor)(sqz)
    exc_step2 = kl.ReLU()(exc_step1)
    exc_step3 = kl.Dense(channels, activation=ka.sigmoid)(exc_step2)
    exc_step4 = kl.multiply([exc_step3, input])
    return exc_step4
def SE_block_maybe(input, use_SE, squeeze_factor=2):
    if not use_SE: 
        return input
    return SE_block(input, squeeze_factor)

# Normalizza le immagini, portando i valori da [0,255] a [-1,1]
def normalize_to_minusone_plusone(input):
    return (input-tf.constant(127.5)) / 128.0

# Costruisce il modello plain, comune ai tre tagli dell'immagine
def plain_model(
    # dimensioni dell'input, lasciate parametriche ma coi valori di default del paper
    # height == numero di righe
    input_height=64, 
    # width == numero di colonne
    input_width=64, 
    input_channels=3, 
    # decide portare le immagini in [-1,1] o tenerle in [0,255]
    # lasciato parametrico per avere l'eventuale possibilità di fare test comparativi
    normalize=True, 
    # decide se usare il blocco squeeze-and-excitation o no.
    # ancora, parametrico per test compartativi.
    use_SE=True,
    # decide in che modo appiattire l'input alla fine del modello
    use_actual_flatten=True
):
    input_layer = kl.Input(shape=(input_height, input_width, input_channels))

    # nome non proprio ortodosso per indicare l'input forse-normalizzato
    block0 = input_layer
    if (normalize):
        block0 = kl.Lambda(normalize_to_minusone_plusone)(block0)
    
    conv1 = kl.Conv2D(32, (3,3), use_bias=False, name="conv1")(block0)
    block1 = B_R_A(conv1)
    block1 = SE_block_maybe(block1, use_SE)

    conv2 = kl.Conv2D(32, (3,3), name="conv2")(block1)
    block2 = B_R_A(conv2)
    block2 = SE_block_maybe(block2, use_SE)

    conv3 = kl.Conv2D(32, (3,3), name="conv3")(block2)
    block3 = B_R_A(conv3)
    block3 = SE_block_maybe(block3, use_SE)

    conv4 = kl.Conv2D(32, (3,3), name="conv4")(block3)
    block4 = B_R(conv4)
    block4 = SE_block_maybe(block4, use_SE)

    conv5 = kl.Conv2D(32, (1,1), name="conv5")(block4)
    block5 = SE_block_maybe(conv5, use_SE)

    if use_actual_flatten:
        flattened = kl.Flatten()(block5)
    else:
        flattened = kl.Reshape((-1,))(block5)
    
    model = keras.Model(inputs=input_layer, outputs=[flattened])

    return model

def full_context_model(
    # parametri per il plain model
    input_height=64, 
    input_width=64, 
    input_channels=3, 
    normalize=True, 
    use_SE=True,
    use_actual_flatten=True,
    # unità della penultima layer
    bottleneck_dim=12
):
    shared_base_model = plain_model(
        input_height, input_width, input_channels, 
        normalize, use_SE, use_actual_flatten
    )

    in1 = kl.Input(shape=(input_height, input_width, input_channels))
    in2 = kl.Input(shape=(input_height, input_width, input_channels))
    in3 = kl.Input(shape=(input_height, input_width, input_channels))

    feat1 = shared_base_model(in1)
    feat2 = shared_base_model(in2)
    feat3 = shared_base_model(in3)

    concatenated_feat = kl.Concatenate(axis=-1)([feat1, feat2, feat3])

    distribution_feat = kl.Dense(
        bottleneck_dim, 
        activity_regularizer = kr.l1(0),
        activation = ka.softmax,
        name="W1"
    )(concatenated_feat)

    age = kl.Dense(1, name="age")(distribution_feat)

    model = keras.Model(inputs=[in1, in2, in3], outputs=[age, distribution_feat])

    return model

if __name__=="__main__":
    print("Hai evocato il test della morte")
    model = full_context_model()
    print(model.summary())
