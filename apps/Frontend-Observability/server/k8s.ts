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
    let res: any;
    try {
      res = await (k8sApi.listNamespacedPod as any)({ namespace });
    } catch (e: any) {
      if (e.statusCode === 404 || e.message?.includes("not assignable") || e.name === "TypeError") {
        res = await (k8sApi.listNamespacedPod as any)(namespace);
      } else {
        throw e;
      }
    }
    
    const items = res.items || res.body?.items || [];
    return items.map((pod: any) => ({
      name: pod.metadata?.name,
      status: pod.status?.phase,
      restarts: pod.status?.containerStatuses?.reduce((acc: number, curr: any) => acc + curr.restartCount, 0) || 0,
      startTime: pod.status?.startTime,
      nodeIP: pod.status?.hostIP,
      podIP: pod.status?.podIP,
      conditions: pod.status?.conditions
    }));
  } catch (err: any) {
    console.error(`Error fetching pods in ${namespace}:`, err);
    throw err;
  }
}

export async function getPodLogs(namespace: string, podName: string) {
  try {
    let res: any;
    try {
      res = await (k8sApi.readNamespacedPodLog as any)({
        name: podName,
        namespace: namespace,
        tailLines: 200,
      });
    } catch (e: any) {
      if (e.statusCode === 404 || e.message?.includes("not assignable") || e.name === "TypeError") {
        res = await (k8sApi.readNamespacedPodLog as any)(
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
      } else {
        throw e;
      }
    }
    return res.body || res;
  } catch (err: any) {
    console.error(`Error fetching logs for ${podName} in ${namespace}:`, err);
    throw err;
  }
}

export async function deletePod(namespace: string, podName: string) {
  try {
    try {
      await (k8sApi.deleteNamespacedPod as any)({
        name: podName,
        namespace: namespace
      });
    } catch (e: any) {
      if (e.statusCode === 404 || e.message?.includes("not assignable") || e.name === "TypeError") {
        await (k8sApi.deleteNamespacedPod as any)(podName, namespace);
      } else {
        throw e;
      }
    }
  } catch (err: any) {
    console.error(`Error deleting pod ${podName} in ${namespace}:`, err);
    throw err;
  }
}
