import os

file_path = '/Users/sujaynimmagadda/Documents/College/Main/inventory-optimization/Frontend/client/src/pages/Stage2Training.tsx'

with open(file_path, 'r') as f:
    content = f.read()

# 1. Update min episodes
content = content.replace(
    'min={10}',
    'min={1}'
)
content = content.replace(
    'if (episodes === "" || Number(episodes) < 10) setEpisodes(10);',
    'if (episodes === "" || Number(episodes) < 1) setEpisodes(1);'
)

# 2. Update Advanced Settings
target_advanced = """                    <CollapsibleContent className="space-y-4 pt-4">
                      <p className="text-xs text-muted-foreground">
                        Each SKU gets its own independent agent with auto-configured parameters.
                      </p>
                    </CollapsibleContent>"""

replacement_advanced = """                    <CollapsibleContent className="space-y-4 pt-4">
                      <p className="text-xs text-muted-foreground">
                        Each SKU gets its own independent agent with auto-configured parameters. Adjust these global hyperparameters if needed.
                      </p>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs">Holding Cost</Label>
                          <Input
                            type="number"
                            min={0.1}
                            step={0.1}
                            value={holdingCost}
                            onChange={(e) => setHoldingCost(e.target.value)}
                            onBlur={() => { if (!holdingCost || Number(holdingCost) <= 0) setHoldingCost(5); }}
                            disabled={isTraining}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">Stockout Penalty</Label>
                          <Input
                            type="number"
                            min={1}
                            step={1}
                            value={stockoutPenalty}
                            onChange={(e) => setStockoutPenalty(e.target.value)}
                            onBlur={() => { if (!stockoutPenalty || Number(stockoutPenalty) <= 0) setStockoutPenalty(200); }}
                            disabled={isTraining}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">Gamma (Discount Factor)</Label>
                          <Input
                            type="number"
                            min={0.1}
                            max={0.999}
                            step={0.01}
                            value={gamma}
                            onChange={(e) => setGamma(e.target.value)}
                            onBlur={() => { if (!gamma || Number(gamma) <= 0 || Number(gamma) >= 1) setGamma(0.98); }}
                            disabled={isTraining}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">Learning Rate</Label>
                          <Input
                            type="number"
                            min={0.00001}
                            max={0.1}
                            step={0.0001}
                            value={learningRate}
                            onChange={(e) => setLearningRate(e.target.value)}
                            onBlur={() => { if (!learningRate || Number(learningRate) <= 0) setLearningRate(0.0001); }}
                            disabled={isTraining}
                          />
                        </div>
                      </div>
                    </CollapsibleContent>"""
content = content.replace(target_advanced, replacement_advanced)

# 3. Add Sweep Mode controls and button
target_controls = """                  </Collapsible>

                  <div className={`grid gap-3 ${isTraining ? 'grid-cols-[1fr_auto]' : 'grid-cols-1'}`}>
                    <Button
                      onClick={handleStartTraining}
                      disabled={isTraining}
                      className="gap-2 h-11 text-sm font-bold shadow-lg shadow-primary/20 w-full"
                    >
                      {isTraining ? (
                        <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                      ) : (
                        <Brain className="w-4 h-4 shrink-0" />
                      )}
                      <span className="truncate">{isTraining ? "Training All SKUs..." : "Start Multi-SKU Training"}</span>
                    </Button>"""

replacement_controls = """                  </Collapsible>

                  <div className="flex items-center gap-2 pt-2 border-t mt-4">
                    <Switch id="sweep-mode" checked={sweepMode} onCheckedChange={setSweepMode} disabled={isTraining || isSweeping} />
                    <Label htmlFor="sweep-mode">Sensitivity Sweep Mode</Label>
                  </div>
                  
                  {sweepMode && (
                    <div className="space-y-4 p-4 bg-muted/20 border rounded-lg mt-2">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs">Parameter to Sweep</Label>
                          <select 
                            className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                            value={sweepParam} 
                            onChange={e => setSweepParam(e.target.value)}
                            disabled={isSweeping}
                          >
                            <option value="learning_rate">Learning Rate</option>
                            <option value="gamma">Gamma</option>
                            <option value="holding_cost">Holding Cost</option>
                            <option value="stockout_penalty">Stockout Penalty</option>
                            <option value="episodes">Episodes</option>
                          </select>
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">Values (comma-separated)</Label>
                          <Input 
                            value={sweepValuesStr} 
                            onChange={e => setSweepValuesStr(e.target.value)} 
                            disabled={isSweeping}
                            placeholder="e.g. 0.001, 0.01, 0.1"
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  <div className={`grid gap-3 ${isTraining || isSweeping ? 'grid-cols-[1fr_auto]' : 'grid-cols-1'}`}>
                    {sweepMode ? (
                      <Button
                        onClick={handleStartSweep}
                        disabled={isSweeping || isTraining}
                        className="gap-2 h-11 text-sm font-bold shadow-lg shadow-primary/20 w-full bg-indigo-600 hover:bg-indigo-700 text-white"
                      >
                        {isSweeping ? <Loader2 className="w-4 h-4 animate-spin shrink-0" /> : <Brain className="w-4 h-4 shrink-0" />}
                        <span className="truncate">{isSweeping ? "Running Sweep..." : "Run Sweep"}</span>
                      </Button>
                    ) : (
                      <Button
                        onClick={handleStartTraining}
                        disabled={isTraining}
                        className="gap-2 h-11 text-sm font-bold shadow-lg shadow-primary/20 w-full"
                      >
                        {isTraining ? (
                          <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                        ) : (
                          <Brain className="w-4 h-4 shrink-0" />
                        )}
                        <span className="truncate">{isTraining ? "Training All SKUs..." : "Start Multi-SKU Training"}</span>
                      </Button>
                    )}"""
content = content.replace(target_controls, replacement_controls)

# 4. Progress condition
content = content.replace(
    '{(isTraining || trainingComplete) && combinedSkuNames.length > 0 && (',
    '{!sweepMode && (isTraining || trainingComplete) && combinedSkuNames.length > 0 && ('
)

# 5. Right column wrap start
target_right_start = """            {/* Right: Per-SKU Reward Chart & Stats */}
            <div className="col-span-1 xl:col-span-2 space-y-6">
              {combinedSkuNames.length > 0 && ("""

replacement_right_start = """            {/* Right: Per-SKU Reward Chart & Stats */}
            <div className="col-span-1 xl:col-span-2 space-y-6">
              {sweepMode ? (
                <Card className="border-border/50 shadow-lg bg-card/50 h-[500px] flex flex-col">
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-primary" /> Sensitivity Sweep Results
                    </CardTitle>
                    <CardDescription>Compare service levels across {sweepParam} values</CardDescription>
                  </CardHeader>
                  <CardContent className="flex-1 min-h-0 relative">
                    {sweepResults.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={sweepResults} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                          <XAxis 
                            dataKey={sweepParam} 
                            label={{ value: sweepParam, position: "insideBottomRight", offset: -10 }} 
                          />
                          <YAxis 
                            domain={[0, 100]} 
                            label={{ value: "Service Level %", angle: -90, position: "insideLeft", offset: -10 }} 
                          />
                          <Tooltip 
                            contentStyle={{ backgroundColor: "hsl(var(--card))", borderRadius: 8 }}
                            formatter={(val: number) => [`${val.toFixed(2)}%`, 'Service Level']}
                          />
                          <Legend />
                          <Line 
                            type="monotone" 
                            dataKey="service_level" 
                            name="Service Level %" 
                            stroke="hsl(var(--primary))" 
                            strokeWidth={3} 
                            dot={{ r: 6 }} 
                            activeDot={{ r: 8 }} 
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-full flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
                        {isSweeping ? (
                          <>
                            <Loader2 className="w-10 h-10 animate-spin text-primary mb-3" />
                            <p className="text-sm font-medium">Running sweep jobs...</p>
                          </>
                        ) : (
                          <>
                            <Activity className="w-10 h-10 mb-3 opacity-10" />
                            <p className="text-sm font-medium">Run sweep to see results</p>
                          </>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ) : (
                <>
                  {combinedSkuNames.length > 0 && ("""
content = content.replace(target_right_start, replacement_right_start)

# 6. Right column wrap end
target_right_end = """              )}
            </div>
          </div>
        </div>
      </main>"""

replacement_right_end = """              )}
                </>
              )}
            </div>
          </div>
        </div>
      </main>"""
content = content.replace(target_right_end, replacement_right_end)

with open(file_path, 'w') as f:
    f.write(content)

print("Patch applied.")
