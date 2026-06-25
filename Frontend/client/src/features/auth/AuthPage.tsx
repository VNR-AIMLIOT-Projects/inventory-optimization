import { useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2 } from "lucide-react";
import { useLocation } from "wouter";
import { ThemeToggle } from "@/components/common/ThemeToggle";

export default function AuthPage() {
  const { loginMutation, registerMutation, user } = useAuth();
  const [, navigate] = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");

  // If already logged in, go to home
  if (user) {
    navigate("/home");
    return null;
  }

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    loginMutation.mutate({ username: email, password });
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    registerMutation.mutate({ username: email, password, firstName, lastName });
  };

  return (
    <div className="min-h-screen flex text-foreground bg-background selection:bg-primary/20 relative overflow-hidden">
      
      <div className="absolute top-6 right-6 z-50">
        <ThemeToggle />
      </div>

      {/* Decorative ambient background */}
      <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] rounded-full bg-primary/5 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-500/5 blur-[120px] pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,hsl(var(--muted-foreground))_1px,transparent_1px),linear-gradient(to_bottom,hsl(var(--muted-foreground))_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none opacity-[0.03] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_40%,#000_80%,transparent_100%)]" />

      {/* Hero / Brand Section */}
      <div className="hidden lg:flex flex-1 flex-col justify-center items-start p-12 lg:p-24 relative z-10 border-r border-border/50 bg-background">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border bg-card shadow-sm mb-8">
          <span className="w-2 h-2 rounded-full bg-primary" />
          <span className="text-xs font-mono text-muted-foreground uppercase">Replenix</span>
        </div>
        
        <h1 className="text-4xl md:text-5xl font-light tracking-tight mb-8 text-foreground">
          Inventory optimization, <br />
          <span className="font-bold">simplified.</span>
        </h1>
        
        {/* Simplified pipeline visual */}
        <div className="w-full max-w-md space-y-4">
          {[
            { step: '1', title: 'Data Pipeline', status: 'Connected' },
            { step: '2', title: 'RL Training', status: 'Optimized' },
            { step: '3', title: 'Deployment', status: 'Live' }
          ].map((item, i) => (
            <div key={i} className="flex items-center gap-4 p-4 rounded-xl border border-border bg-card">
              <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">
                {item.step}
              </div>
              <div className="flex-1">
                <p className="font-medium text-sm">{item.title}</p>
                <p className="text-xs text-muted-foreground">{item.status}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Form Section */}
      <div className="flex-1 flex flex-col justify-center px-4 sm:px-12 py-12 lg:py-24 relative z-10">
        <div className="mx-auto w-full max-w-sm">
          
          <div className="flex flex-col items-center lg:items-start mb-8">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">Welcome Back</h2>
            <p className="text-muted-foreground text-sm mt-2 font-light">Enter your email and password</p>
          </div>

          <Tabs defaultValue="login" className="w-full">
            <TabsList className="grid w-full grid-cols-2 mb-6 bg-muted p-1 rounded-lg">
              <TabsTrigger value="login" className="rounded-md">Sign in</TabsTrigger>
              <TabsTrigger value="register" className="rounded-md">Create account</TabsTrigger>
            </TabsList>
            
            <TabsContent value="login" className="mt-0">
              <Card className="border-border shadow-sm bg-card">
                <form onSubmit={handleLogin}>
                  <CardHeader className="p-4 pb-4">
                    <CardTitle className="text-base">Sign in</CardTitle>
                    <CardDescription>Sign in to your account</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4 p-4 pt-0">
                    <div className="space-y-2">
                      <Label htmlFor="login-email">Email</Label>
                      <Input id="login-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-10" placeholder="user@example.com" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="login-password">Password</Label>
                      <Input id="login-password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="h-10" placeholder="••••••••" />
                    </div>
                    <Button type="submit" className="w-full h-10 font-medium mt-4" disabled={loginMutation.isPending}>
                      {loginMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                      Sign in
                    </Button>
                  </CardContent>
                </form>
              </Card>
            </TabsContent>
            
            <TabsContent value="register" className="mt-0">
              <Card className="border-border shadow-sm bg-card">
                <form onSubmit={handleRegister}>
                  <CardHeader className="p-4 pb-4">
                    <CardTitle className="text-base">Create your account</CardTitle>
                    <CardDescription>Enter your details below to get started.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4 p-4 pt-0">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="reg-first">First Name</Label>
                        <Input id="reg-first" required value={firstName} onChange={(e) => setFirstName(e.target.value)} className="h-10" placeholder="John" />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="reg-last">Last Name</Label>
                        <Input id="reg-last" required value={lastName} onChange={(e) => setLastName(e.target.value)} className="h-10" placeholder="Doe" />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="reg-email">Email</Label>
                      <Input id="reg-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-10" placeholder="user@example.com" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="reg-password">Password</Label>
                      <Input id="reg-password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="h-10" placeholder="••••••••" />
                    </div>
                    <Button type="submit" className="w-full h-10 font-medium mt-4" disabled={registerMutation.isPending}>
                      {registerMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                      Create account
                    </Button>
                  </CardContent>
                </form>
              </Card>
            </TabsContent>
          </Tabs>

        </div>
      </div>
    </div>
  );
}
