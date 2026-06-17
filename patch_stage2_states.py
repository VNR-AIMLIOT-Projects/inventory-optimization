import os

file_path = '/Users/sujaynimmagadda/Documents/College/Main/inventory-optimization/Frontend/client/src/pages/Stage2Training.tsx'

with open(file_path, 'r') as f:
    content = f.read()

# Add API imports
content = content.replace(
    '  loadTrainingRun,\n} from "@/lib/api";',
    '  loadTrainingRun,\n  startSweepTraining,\n  getSweepResults,\n} from "@/lib/api";'
)

# Add state variables
state_vars = """  const [episodes, setEpisodes] = useState<number | string>(500);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const [holdingCost, setHoldingCost] = useState<number | string>(5);
  const [stockoutPenalty, setStockoutPenalty] = useState<number | string>(200);
  const [gamma, setGamma] = useState<number | string>(0.98);
  const [learningRate, setLearningRate] = useState<number | string>(0.0001);

  const [sweepMode, setSweepMode] = useState(false);
  const [sweepParam, setSweepParam] = useState("learning_rate");
  const [sweepValuesStr, setSweepValuesStr] = useState("0.0001, 0.001, 0.01");
  const [isSweeping, setIsSweeping] = useState(false);
  const [sweepResults, setSweepResults] = useState<{ sweep_param_value: number; service_level: number }[]>([]);
  const sweepPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startSweepPolling = (runId: string) => {
    if (sweepPollingRef.current) clearInterval(sweepPollingRef.current);
    
    sweepPollingRef.current = setInterval(async () => {
      try {
        const res = await getSweepResults(runId);
        if (res.status === 'completed' || res.status === 'failed') {
          if (sweepPollingRef.current) clearInterval(sweepPollingRef.current);
          setIsSweeping(false);
          if (res.results) {
            setSweepResults(res.results);
          }
        } else if (res.status === 'running') {
          if (res.results) {
            setSweepResults(res.results);
          }
        }
      } catch (err) {
        console.error("Sweep poll error:", err);
      }
    }, 2000);
  };

  const handleStartSweep = async () => {
    try {
      setIsSweeping(true);
      setSweepResults([]);
      
      const paramMap: Record<string, string> = {
        "learning_rate": "learning_rate",
        "gamma": "gamma",
        "holding_cost": "holding_cost",
        "stockout_penalty": "stockout_penalty",
        "episodes": "episodes"
      };

      const sweepValues = sweepValuesStr.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v));
      if (sweepValues.length === 0) {
        toast({ title: "Error", description: "Please enter valid sweep values", variant: "destructive" });
        setIsSweeping(false);
        return;
      }

      const payload = {
        episodes: Number(episodes),
        holding_cost: Number(holdingCost),
        stockout_penalty: Number(stockoutPenalty),
        gamma: Number(gamma),
        learning_rate: Number(learningRate),
        sweep_param: paramMap[sweepParam] || "learning_rate",
        sweep_values: sweepValues
      };

      const res = await startSweepTraining(payload);
      toast({
        title: "Sweep Started",
        description: res.message
      });
      
      startSweepPolling(res.sweep_run_id);
    } catch (err: any) {
      setIsSweeping(false);
      toast({
        title: "Failed to start sweep",
        description: friendlyError(err),
        variant: "destructive",
      });
    }
  };
"""

content = content.replace(
    '  const [episodes, setEpisodes] = useState<number | string>(500);\n  const [advancedOpen, setAdvancedOpen] = useState(false);',
    state_vars
)

with open(file_path, 'w') as f:
    f.write(content)

print("Added state variables.")
