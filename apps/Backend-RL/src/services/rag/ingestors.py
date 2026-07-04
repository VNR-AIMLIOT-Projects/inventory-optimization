def chunk_training_run(row: dict) -> str:
    """Formats a training_runs row into a RAG chunk."""
    return (
        f"Training Run #{row.get('id')} | SKU: {row.get('sku')} | "
        f"Status: {row.get('status')} | Episodes: {row.get('episodes')} | "
        f"Best Reward: {row.get('best_reward')} | "
        f"Avg Reward (final): {row.get('final_avg_reward')} | "
        f"Holding Cost: {row.get('holding_cost')} | Stockout Penalty: {row.get('stockout_penalty')} | "
        f"Completed: {row.get('completed_at')}"
    )

def chunk_eval_result(row: dict) -> str:
    """Formats an evaluation_results row into a RAG chunk."""
    rl = row.get('rl_reward')
    oracle = row.get('oracle_reward')
    
    efficiency = 0
    if rl is not None and oracle is not None and oracle != 0:
        efficiency = (rl / oracle) * 100
        
    return (
        f"Evaluation Result | SKU: {row.get('sku')} | Run #{row.get('training_run_id')} | "
        f"RL Reward: {rl} | Oracle Reward: {oracle} | "
        f"Rule Reward: {row.get('rule_reward')} | RL Efficiency: {efficiency:.1f}% of oracle | "
        f"Evaluated: {row.get('created_at')}"
    )

def chunk_demand_model(row: dict) -> str:
    """Formats a demand_models row into a RAG chunk."""
    return (
        f"Demand Model | SKU: {row.get('sku')} | "
        f"Baseline: {row.get('baseline_start')} units/day | "
        f"Seasonal Peak: {row.get('seasonal_peak')} units/day | "
        f"Festival Peak: {row.get('festival_peak')} units/day | "
        f"Num Days: {row.get('num_days')} | Created: {row.get('created_at')}"
    )

def chunk_deployment_session(row: dict) -> str:
    """Formats a deployment_sessions row into a RAG chunk."""
    return (
        f"Deployment Session | ID: {row.get('id')} | SKU: {row.get('sku')} | "
        f"Run #{row.get('run_id')} | Status: {row.get('status')} | "
        f"Current Day: {row.get('current_day')} | "
        f"Initial Inventory: {row.get('initial_inventory')} | "
        f"Started: {row.get('created_at')}"
    )
