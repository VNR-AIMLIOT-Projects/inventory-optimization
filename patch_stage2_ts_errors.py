import os

file_path = '/Users/sujaynimmagadda/Documents/College/Main/inventory-optimization/Frontend/client/src/pages/Stage2Training.tsx'

with open(file_path, 'r') as f:
    content = f.read()

# 1. Add Switch import
content = content.replace(
    'import { Progress } from "@/components/ui/progress";',
    'import { Progress } from "@/components/ui/progress";\nimport { Switch } from "@/components/ui/switch";'
)

# 2. Fix sweepResults type
content = content.replace(
    'const [sweepResults, setSweepResults] = useState<{ sweep_param_value: number; service_level: number }[]>([]);',
    'const [sweepResults, setSweepResults] = useState<any[]>([]);'
)

# 3. Fix SweepRequest payload
old_payload = """      const payload = {
        episodes: Number(episodes),
        holding_cost: Number(holdingCost),
        stockout_penalty: Number(stockoutPenalty),
        gamma: Number(gamma),
        learning_rate: Number(learningRate),
        sweep_param: paramMap[sweepParam] || "learning_rate",
        sweep_values: sweepValues
      };"""

new_payload = """      const payload = {
        base_params: {
          episodes: Number(episodes),
          holding_cost: Number(holdingCost),
          stockout_penalty: Number(stockoutPenalty),
          gamma: Number(gamma),
          learning_rate: Number(learningRate)
        },
        sweep_param: paramMap[sweepParam] || "learning_rate",
        sweep_values: sweepValues
      };"""
content = content.replace(old_payload, new_payload)

# 4. Fix sweep_id
content = content.replace(
    'startSweepPolling(res.sweep_run_id);',
    'startSweepPolling(res.sweep_id);'
)

with open(file_path, 'w') as f:
    f.write(content)

print("TS errors patched.")
