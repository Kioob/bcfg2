""" Reporting Transport that stores statistics data directly in the
storage backend """

import os
import sys
import threading
from Bcfg2.Reporting.Transport.base import TransportBase, TransportError
from Bcfg2.Reporting.Storage import load_storage_from_config
from Bcfg2.Compat import Queue, Full, Empty, cPickle


class DirectStore(TransportBase, threading.Thread):
    def __init__(self, setup):
        TransportBase.__init__(self, setup)
        threading.Thread.__init__(self)
        self.save_file = os.path.join(self.data, ".saved")
        self.storage = load_storage_from_config(setup)
        self.queue = Queue(100000)
        self.terminate = threading.Event()
        self.start()

    def shutdown(self):
        self.terminate.set()

    def store(self, hostname, metadata, stats):
        try:
            self.queue.put_nowait(dict(
                    hostname=hostname,
                    metadata=metadata,
                    stats=stats))
        except Full:
            self.logger.warning("Reporting: Queue is full, "
                                "dropping statistics")

    def run(self):
        if not self._load():
            return
        while not self.terminate.isSet() and self.queue is not None:
            try:
                interaction = self.queue.get(block=True,
                                             timeout=self.timeout)
                self.storage.import_interaction(interaction)
            except Empty:
                continue
            except:
                err = sys.exc_info()[1]
                self.logger.error("Reporting: Could not import interaction: %s"
                                  % err)
                continue
        if self.queue is not None and not self.queue.empty():
            self._save()

    def fetch(self):
        """ no collector is necessary with this backend """
        pass

    def start_monitor(self, collector):
        """ no collector is necessary with this backend """
        pass

    def rpc(self, method, *args, **kwargs):
        try:
            return getattr(self.storage, method)(*args, **kwargs)
        except:  # pylint: disable=W0702
            msg = "Reporting: RPC method %s failed: %s" % (method,
                                                           sys.exc_info()[1])
            self.logger.error(msg)
            raise TransportError(msg)

    def _save(self):
        """ Save any saved data to a file """
        saved_data = []
        try:
            while not self.queue.empty():
                saved_data.append(self.queue.get_nowait())
        except Empty:
            pass

        try:
            savefile = open(self.save_file, 'w')
            cPickle.dump(saved_data, savefile)
            savefile.close()
            self.logger.info("Saved pending Reporting data")
        except (IOError, TypeError):
            err = sys.exc_info()[1]
            self.logger.warning("Failed to save pending data: %s" % err)

    def _load(self):
        """ Load any saved data from a file """
        if not os.path.exists(self.save_file):
            return True
        saved_data = []
        try:
            savefile = open(self.save_file, 'r')
            saved_data = cPickle.load(savefile)
            savefile.close()
        except (IOError, cPickle.UnpicklingError):
            err = sys.exc_info()[1]
            self.logger.warning("Failed to load saved data: %s" % err)
            return False
        for interaction in saved_data:
            # check that shutdown wasnt called early
            if self.terminate.isSet():
                return False

            try:
                self.queue.put_nowait(interaction)
            except Full:
                self.logger.warning("Reporting: Queue is full, failed to "
                                    "load saved interaction data")
                break
        try:
            os.unlink(self.save_file)
        except OSError:
            self.logger.error("Reporting: Failed to unlink save file: %s" %
                              self.save_file)
        self.logger.info("Reporting: Loaded saved interaction data")
        return True
