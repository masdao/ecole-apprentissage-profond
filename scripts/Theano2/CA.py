# Source: https://github.com/lisa-lab/DeepLearningTutorials/blob/master/code/cA.py

import numpy as np

import theano
import theano.tensor as T
from theano.sandbox.rng_mrg import MRG_RandomStreams as RandomStreams

from utils import load_data
from utils import tile_raster_images

class CA(object):

    def __init__(
        self,
        numpy_rng,
        theano_rng,
        input,
        n_visible,
        n_hidden,
        W=None,
        bhid=None,
        bvis=None,
        batch_size=1
    ):
        """

        :type numpy_rng: numpy.random.RandomState
        :param numpy_rng: number random generator used to generate weights

        :type theano_rng: theano.tensor.shared_randomstreams.RandomStreams
        :param theano_rng: Theano random generator; if None is given one is
                     generated based on a seed drawn from `rng`

        :type input: theano.tensor.TensorType
        :param input: a symbolic description of the input or None for
                      standalone dA

        :type n_visible: int
        :param n_visible: number of visible units

        :type n_hidden: int
        :param n_hidden:  number of hidden units

        :type W: theano.tensor.TensorType
        :param W: Theano variable pointing to a set of weights that should be
                  shared belong the dA and another architecture; if dA should
                  be standalone set this to None

        :type bhid: theano.tensor.TensorType
        :param bhid: Theano variable pointing to a set of biases values (for
                     hidden units) that should be shared belong dA and another
                     architecture; if dA should be standalone set this to None

        :type bvis: theano.tensor.TensorType
        :param bvis: Theano variable pointing to a set of biases values (for
                     visible units) that should be shared belong dA and another
                     architecture; if dA should be standalone set this to None


        """

        # instance variables
        self.numpy_rng = numpy_rng
        self.theano_rng = theano_rng # NOT USED
        self.input = input
        self.n_visible = n_visible
        self.n_hidden = n_hidden
        self.W = W
        self.W_prime = None
        self.bhid = bhid
        self.bvis = bvis
        self.b = None
        self.b_prime = None
        self.batch_size = batch_size

        self.initialize_variables()

        self.params = [self.W, self.b, self.b_prime]

    def initialize_variables(self):
        # create a Theano random generator that gives symbolic random values
        

        # note : W' was written as `W_prime` and b' as `b_prime`
        if not self.W:
            # W is initialized with `initial_W` which is uniformely sampled
            # from -4*sqrt(6./(n_visible+n_hidden)) and
            # 4*sqrt(6./(n_hidden+n_visible))the output of uniform if
            # converted using asarray to dtype
            # theano.config.floatX so that the code is runable on GPU
            initial_W = np.asarray(
                self.numpy_rng.uniform(
                    low=-4 * np.sqrt(6. / (self.n_hidden + self.n_visible)),
                    high=4 * np.sqrt(6. / (self.n_hidden + self.n_visible)),
                    size=(self.n_visible, self.n_hidden)
                ),
                dtype=theano.config.floatX
            )
            self.W = theano.shared(value=initial_W, name='W', borrow=True)

        if not self.bvis:
            self.bvis = theano.shared(
                value=np.zeros(
                    self.n_visible,
                    dtype=theano.config.floatX
                ),
                borrow=True
            )

        if not self.bhid:
            self.bhid = theano.shared(
                value=np.zeros(
                    self.n_hidden,
                    dtype=theano.config.floatX
                ),
                name='b',
                borrow=True
            )

        # tied weights, therefore W_prime is W transpose
        self.W_prime = self.W.T
        # b corresponds to the bias of the hidden
        self.b = self.bhid
        # b_prime corresponds to the bias of the visible
        self.b_prime = self.bvis

        # if no input is given, generate a variable representing the input
        if self.input is None:
            # we use a matrix because we expect a minibatch of several
            # examples, each example being a row
            self.x = T.dmatrix(name='input')
        else:
            self.x = self.input


    def get_hidden_values(self, input):
        """ Computes the values of the hidden layer """
        return T.nnet.sigmoid(T.dot(input, self.W) + self.b)

    def get_jacobian(self, hidden, W):
        """Computes the jacobian of the hidden layer with respect to
        the input, reshapes are necessary for broadcasting the
        element-wise product on the right axis
        """
        return T.reshape(hidden * (1 - hidden), (self.batch_size, 1, self.n_hidden)) \
                            * T.reshape(W, (1, self.n_visible, self.n_hidden))

    def get_reconstructed_input(self, hidden):
        """Computes the reconstructed input given the values of the
        hidden layer

        """
        return T.nnet.sigmoid(T.dot(hidden, self.W_prime) + self.b_prime)

    def cost(self, contraction_level):
        y = self.get_hidden_values(self.x)
        z = self.get_reconstructed_input(y)
        J = self.get_jacobian(y, self.W)
        # note : we sum over the size of a datapoint; if we are using
        #        minibatches, L will be a vector, with one entry per
        #        example in minibatch
        L = - T.sum(self.x * T.log(z) + (1 - self.x) * T.log(1 - z), axis=1)
        # note : L is now a vector, where each element is the
        #        cross-entropy cost of the reconstruction of the
        #        corresponding example of the minibatch. We need to
        #        compute the average of all these to get the cost of
        #        the minibatch

        # Compute the jacobian and average over the number of samples/minibatch
        L_jacob = T.sum(J ** 2) / self.batch_size

        cost = T.mean(L) + contraction_level * T.mean(L_jacob)
        return cost

    def updates(self, cost, learning_rate):
        grads = T.grad(cost, self.params)
        updates = [
            (param, param - learning_rate * gparam)
            for param, gparam in zip(self.params, grads)
        ]
        return updates

    def get_cost_updates(self, contraction_level, learning_rate):
        cost = self.cost(contraction_level)
        updates = self.updates(cost, learning_rate)
        
        return cost, updates