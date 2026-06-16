import { Sidebar } from "@/components/common/Sidebar";
import { Header } from "@/components/common/Header";
import { usePendingDecisions } from "@/hooks/use-decisions";
import { useSimulationState, useStepSimulation } from "@/hooks/use-simulation";
import { DecisionCard } from "@/features/deployment/components/DecisionCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Play, ClipboardCheck, History } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function AgentMonitor() {
  const { data: pendingDecisions } = usePendingDecisions();
  const { data: simState } = useSimulationState();
  const { mutate: step } = useStepSimulation();

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-64 flex flex-col h-screen overflow-hidden">
        <Header title="Automation Queue" />
        
        <div className="flex-1 p-8 grid grid-cols-12 gap-8 overflow-hidden">
          <div className="col-span-5 flex flex-col gap-6 overflow-hidden h-full">
            <Card className="flex-none border-border/50 bg-gradient-to-br from-card to-muted/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Play className="w-4 h-4 text-primary" />
                  Execution Control
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Button onClick={() => step(undefined)} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground">
                  Proceed to Next Day
                </Button>
                <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground bg-muted/30 p-2 rounded-lg border border-border">
                  <span>Status:</span>
                  <Badge variant="outline" className="text-[10px] h-4 border-green-500/50 text-green-500 bg-green-500/10">Automated Agent Online</Badge>
                </div>
              </CardContent>
            </Card>

            <div className="flex-1 flex flex-col min-h-0">
              <h3 className="text-lg font-medium mb-4 flex items-center gap-2">
                <ClipboardCheck className="w-5 h-5 text-yellow-500" />
                Awaiting Verification 
                <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-500">{pendingDecisions?.length || 0}</Badge>
              </h3>
              
              <div className="flex-1 overflow-y-auto pr-2 space-y-4 pb-4">
                <AnimatePresence>
                  {pendingDecisions?.length === 0 ? (
                    <motion.div 
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="h-full flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl p-8"
                    >
                      <p className="text-sm">No pending tasks</p>
                      <p className="text-xs mt-1">Automation is in sync with inventory</p>
                    </motion.div>
                  ) : (
                    pendingDecisions?.map((decision) => (
                      <DecisionCard key={decision.id} decision={decision} />
                    ))
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>

          <div className="col-span-7 flex flex-col h-full overflow-hidden">
             <Card className="h-full flex flex-col border-border/50 shadow-lg">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <History className="w-5 h-5 text-muted-foreground" />
                  Operational Log
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 overflow-hidden p-0">
                <div className="h-full overflow-auto">
                  <Table>
                    <TableHeader className="bg-muted/50 sticky top-0 z-10 backdrop-blur-sm">
                      <TableRow className="border-border/50">
                        <TableHead className="w-[80px]">Day</TableHead>
                        <TableHead>Stock</TableHead>
                        <TableHead>Orders</TableHead>
                        <TableHead>Fulfillment</TableHead>
                        <TableHead>Arrived</TableHead>
                        <TableHead className="text-right">Profit</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {simState?.recentHistory?.slice().reverse().map((day) => (
                        <TableRow key={day.id} className="border-border/50 hover:bg-muted/30">
                          <TableCell className="font-mono font-medium text-muted-foreground">#{day.day}</TableCell>
                          <TableCell className="text-blue-400 font-medium">{day.inventoryLevel}</TableCell>
                          <TableCell>{day.demand}</TableCell>
                          <TableCell className={`${day.lostSales > 0 ? 'text-red-400 font-bold' : 'text-green-400'}`}>
                            {((day.unitsSold / day.demand) * 100).toFixed(0)}%
                          </TableCell>
                          <TableCell className={`${(day.replenishmentOrders || 0) > 0 ? 'text-primary font-bold' : 'text-muted-foreground'}`}>{day.replenishmentOrders}</TableCell>
                          <TableCell className="text-right font-mono">${Number(day.reward).toFixed(0)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
