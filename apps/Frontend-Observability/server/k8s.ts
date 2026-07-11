import * as k8s from "@kubernetes/client-node";

// Load kubeconfig
const kc = new k8s.KubeConfig();
try {
  kc.loadFromCluster();
} catch (e) {
  console.log("Could not load from cluster, loading from default.");
  kc.loadFromDefault();
}

const k8sApi = kc.makeApiClient(k8s.CoreV1Api);

export async function getPods(namespace: string) {
  try {
    // Note: The method signature may vary based on the version of @kubernetes/client-node.
    // Try passing namespace as the first positional argument, which is widely supported.
    const res = await (k8sApi.listNamespacedPod as any)({ namespace });
    return res.items.map((pod: any) => ({
      name: pod.metadata?.name,
      status: pod.status?.phase,
      restarts: pod.status?.containerStatuses?.reduce((acc: number, curr: any) => acc + curr.restartCount, 0) || 0,
      startTime: pod.status?.startTime,
      nodeIP: pod.status?.hostIP,
      podIP: pod.status?.podIP,
      conditions: pod.status?.conditions
    }));
  } catch (err: any) {
    if (err.statusCode === 404) {
      // Maybe different method signature
      const res = await (k8sApi.listNamespacedPod as any)(namespace);
      return res.body.items.map((pod: any) => ({
        name: pod.metadata?.name,
        status: pod.status?.phase,
        restarts: pod.status?.containerStatuses?.reduce((acc: number, curr: any) => acc + curr.restartCount, 0) || 0,
        startTime: pod.status?.startTime,
        nodeIP: pod.status?.hostIP,
        podIP: pod.status?.podIP,
        conditions: pod.status?.conditions
      }));
    }
    console.error(`Error fetching pods in ${namespace}:`, err);
    throw err;
  }
}

export async function getPodLogs(namespace: string, podName: string) {
  try {
    const res = await (k8sApi.readNamespacedPodLog as any)({
      name: podName,
      namespace: namespace,
      tailLines: 200,
    });
    return res;
  } catch (err: any) {
    if (err.statusCode === 404) {
       const res = await (k8sApi.readNamespacedPodLog as any)(
        podName,
        namespace,
        undefined, // container
        undefined, // follow
        undefined, // limitBytes
        undefined, // pretty
        undefined, // previous
        undefined, // sinceSeconds
        200,       // tailLines
        undefined  // timestamps
      );
      return res.body;
    }
    console.error(`Error fetching logs for ${podName} in ${namespace}:`, err);
    throw err;
  }
}

export async function deletePod(namespace: string, podName: string) {
  try {
    await (k8sApi.deleteNamespacedPod as any)({
      name: podName,
      namespace: namespace
    });
  } catch (err: any) {
    if (err.statusCode === 404) {
      await (k8sApi.deleteNamespacedPod as any)(podName, namespace);
      return;
    }
    console.error(`Error deleting pod ${podName} in ${namespace}:`, err);
    throw err;
  }
}
