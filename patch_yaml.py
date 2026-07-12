with open("k8s/monitoring/insights-agent-cronjob.yaml", "r") as f:
    content = f.read()

target = """            - name: NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace"""

replacement = """            - name: NAMESPACES
              value: "replenix-prod,replenix-preprod" """

content = content.replace(target, replacement)

with open("k8s/monitoring/insights-agent-cronjob.yaml", "w") as f:
    f.write(content)
print("Patched YAML")
