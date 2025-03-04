from __future__ import print_function
from datetime import datetime
# A quick fix to run TF 1.X code in TF 2.X, we may want to properly migrate the Python script to TF 2.X API.
import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()
import sys
import time
import json
from tensorflow.python.summary.writer.writer_cache import FileWriterCache as SummaryWriterCache
import tensorflow_on_flink.tensorflow_on_flink_ops as tff_ops
import traceback


def log_speed(steps, start):
    duration = time.time() - start
    speed = steps / duration
    print ("Read directly: " + str(steps) + " steps, at " + '%.2f' % speed + " steps/second")
    sys.stdout.flush()


def map_fun(context):
    print(tf.__version__)
    sys.stdout.flush()
    tf.logging.set_verbosity(tf.logging.ERROR)
    jobName = context.jobName
    index = context.index
    clusterStr = context.properties["cluster"]
    delim = context.properties["SYS:delim"]
    epochs = int(context.properties["epochs"])
    data_file = context.properties["data.file"]
    print (index, clusterStr)
    sys.stdout.flush()
    clusterJson = json.loads(clusterStr)
    cluster = tf.train.ClusterSpec(cluster=clusterJson)
    server = tf.train.Server(cluster, job_name=jobName, task_index=index)
    sess_config = tf.ConfigProto(allow_soft_placement=True, log_device_placement=False,
                                 device_filters=["/job:ps", "/job:worker/task:%d" % index])

    with tf.device(tf.train.replica_device_setter(worker_device='/job:worker/task:' + str(index), cluster=cluster)):
        filename_queue = tf.train.string_input_producer([data_file], num_epochs=epochs)
        reader = tf.TextLineReader()
        key, value = reader.read(filename_queue)
        global_step = tf.train.get_or_create_global_step()
        global_step_inc = tf.assign_add(global_step, 1)
        is_chief = (index == 0)
        print (datetime.now().isoformat() + " started ------------------------------------")
        t = time.time()
        total_step = 0
        try:
            with tf.train.MonitoredTrainingSession(master=server.target, is_chief=is_chief, config=sess_config,
                                                   checkpoint_dir="./target/tmp/input_output/" + str(t)) as mon_sess:
                # while not mon_sess.should_stop():
                while True:
                    total_step, _, _ = mon_sess.run([global_step_inc, key, value])
                    if (total_step % 10000 == 0):
                        log_speed(total_step, t)
        except Exception as e:
            print('traceback.print_exc():')
            traceback.print_exc()
            sys.stdout.flush()
        finally:
            print (datetime.now().isoformat() + " ended --------------------------------------")
            log_speed(total_step, t)
            SummaryWriterCache.clear()


if __name__ == "__main__":
    map_fun(context)
