"""Kubernetes client for the controller (R5, owner: Rishabh).

Inside the cluster it uses the Pod's ServiceAccount. If KUBE_TARGET_KUBECONFIG
is set (R1 options B and C, or local development), it targets that cluster.
Outside a cluster it never falls back to your default kubeconfig, because that
could point at an unrelated cluster.
"""

import os
from pathlib import Path

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

SA_NAMESPACE_FILE = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")


def core_api() -> client.CoreV1Api:
    target = os.getenv("KUBE_TARGET_KUBECONFIG")
    if target:
        config.load_kube_config(config_file=target)
    else:
        try:
            config.load_incluster_config()
        except ConfigException as err:
            raise RuntimeError(
                "Not in a cluster and KUBE_TARGET_KUBECONFIG is not set. "
                "Set it to the kubeconfig of the cluster the controller should manage."
            ) from err
    return client.CoreV1Api()


def namespace() -> str:
    """The namespace for attendee Pods: POD_NAMESPACE, else the ServiceAccount's namespace."""
    if os.getenv("POD_NAMESPACE"):
        return os.environ["POD_NAMESPACE"]
    if SA_NAMESPACE_FILE.exists():
        return SA_NAMESPACE_FILE.read_text().strip()
    return "default"
