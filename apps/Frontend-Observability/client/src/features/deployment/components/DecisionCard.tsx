import { AgentDecision } from "@shared/schema";
import { useReviewDecision } from "@/hooks/use-decisions";
import { Check, X, Edit2, AlertCircle, Zap, TrendingUp } from "lucide-react";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";

interface DecisionCardProps {
  decision: AgentDecision;
}

export function DecisionCard({ decision }: DecisionCardProps) {
  const { mutate: review, isPending } = useReviewDecision();
  const [isOverrideOpen, setIsOverrideOpen] = useState(false);
  const [overrideValue, setOverrideValue] = useState(decision.proposedAction.toString());

  const handleApprove = () => review({ id: decision.id, status: "approved" });
  const handleReject = () => review({ id: decision.id, status: "rejected" });
  const handleOverride = () => {
    review({ id: decision.id, status: "overridden", overrideValue: parseInt(overrideValue) });
    setIsOverrideOpen(false);
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      layout
      className="bg-card border border-border/50 rounded-xl p-5 shadow-lg hover:shadow-xl hover:border-primary/20 transition-all duration-300 relative group overflow-hidden"
    >
      <div className="absolute top-0 left-0 w-1 h-full bg-yellow-500/50" />
      
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-yellow-500/10 flex items-center justify-center">
            <Zap className="w-5 h-5 text-yellow-500" />
          </div>
          <div>
            <h4 className="font-semibold text-foreground">Inventory Task</h4>
            <p className="text-xs text-muted-foreground">Day {decision.simulationDay}</p>
          </div>
        </div>
        <div className="flex items-center gap-1 bg-muted px-2 py-1 rounded-md">
          <TrendingUp className="w-3 h-3 text-emerald-400" />
          <span className="text-xs font-mono font-medium">{Number(decision.confidence) * 100}% Conf.</span>
        </div>
      </div>

      <div className="space-y-3 mb-6">
        <div className="flex justify-between items-end">
          <span className="text-sm text-muted-foreground">Proposed Quantity</span>
          <span className="text-2xl font-display font-bold text-foreground">{decision.proposedAction} <span className="text-sm font-sans font-normal text-muted-foreground">units</span></span>
        </div>
        
        {decision.reasoning && (
          <div className="bg-muted/30 p-3 rounded-lg border border-border/50">
            <p className="text-sm text-muted-foreground italic">"{decision.reasoning}"</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2">
        <button 
          onClick={handleApprove}
          disabled={isPending}
          className="flex flex-col items-center justify-center p-2 rounded-lg bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500 hover:text-white transition-all duration-200 border border-emerald-500/20"
        >
          <Check className="w-5 h-5 mb-1" />
          <span className="text-xs font-medium">Approve</span>
        </button>

        <button 
          onClick={handleReject}
          disabled={isPending}
          className="flex flex-col items-center justify-center p-2 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500 hover:text-white transition-all duration-200 border border-red-500/20"
        >
          <X className="w-5 h-5 mb-1" />
          <span className="text-xs font-medium">Reject</span>
        </button>

        <button 
          onClick={() => setIsOverrideOpen(true)}
          disabled={isPending}
          className="flex flex-col items-center justify-center p-2 rounded-lg bg-blue-500/10 text-blue-500 hover:bg-blue-500 hover:text-white transition-all duration-200 border border-blue-500/20"
        >
          <Edit2 className="w-5 h-5 mb-1" />
          <span className="text-xs font-medium">Override</span>
        </button>
      </div>

      <Dialog open={isOverrideOpen} onOpenChange={setIsOverrideOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Override Decision</DialogTitle>
            <DialogDescription>
              The agent proposed <strong>{decision.proposedAction}</strong> units. Enter a new value below manually.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input 
              type="number" 
              value={overrideValue} 
              onChange={(e) => setOverrideValue(e.target.value)}
              className="text-lg font-mono"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOverrideOpen(false)}>Cancel</Button>
            <Button onClick={handleOverride}>Confirm Override</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
