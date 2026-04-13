import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";
import { Loader2, UserCircle } from "lucide-react";

export default function ProfilePage() {
  const { isCollapsed } = useSidebar();
  const { user } = useAuth();
  const { toast } = useToast();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");

  useEffect(() => {
    if (user) {
      setFirstName(user.firstName || "");
      setLastName(user.lastName || "");
    }
  }, [user]);

  const updateProfileMutation = useMutation({
    mutationFn: async (data: { firstName: string; lastName: string }) => {
      const res = await apiRequest("PATCH", "/api/user", data);
      if (!res.ok) throw new Error("Failed to update profile");
      return await res.json();
    },
    onSuccess: (updatedUser) => {
      queryClient.setQueryData(["/api/user"], updatedUser);
      toast({
        title: "Profile Updated",
        description: "Your personal information has been saved successfully.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Error",
        description: err.message,
        variant: "destructive",
      });
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateProfileMutation.mutate({ firstName, lastName });
  };

  return (
    <div className="flex min-h-screen bg-background text-foreground font-sans selection:bg-primary/20">
      <Sidebar />
      <main className={cn("flex-1 flex flex-col relative z-10 transition-all duration-300", isCollapsed ? "lg:ml-[112px]" : "lg:ml-[288px]")}>
        <Header title="My Profile" />

        <div className="px-6 pb-16 pt-8 space-y-4 animate-in fade-in duration-500 max-w-3xl mx-auto w-full">
          
          <div className="mb-12 border-l-2 border-primary/50 pl-6 py-2">
            <h1 className="text-4xl font-light tracking-tight mb-4 text-foreground flex items-center gap-4">
              <UserCircle className="w-10 h-10 text-primary" />
              Operator <span className="font-bold">Identity</span>
            </h1>
            <p className="text-muted-foreground text-lg max-w-2xl font-light leading-relaxed">
              Manage your personal credentials and identity profiles across the Replenix environment.
            </p>
          </div>

          <Card className="border-border/50 shadow-lg bg-card/50 backdrop-blur-sm">
            <form onSubmit={handleSubmit}>
              <CardHeader>
                <CardTitle>Personal Information</CardTitle>
                <CardDescription>Update your contact details and display name.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                
                <div className="space-y-2">
                  <Label className="text-xs uppercase tracking-wider text-muted-foreground">Email Address (Read Only)</Label>
                  <Input readOnly value={user?.username || ""} className="bg-muted cursor-not-allowed opacity-70" />
                  <p className="text-[10px] text-muted-foreground/70">Your primary identifier cannot be changed once initialized.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="firstName" className="text-xs uppercase tracking-wider text-muted-foreground">First Name</Label>
                    <Input id="firstName" value={firstName} onChange={e => setFirstName(e.target.value)} className="bg-background/50" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="lastName" className="text-xs uppercase tracking-wider text-muted-foreground">Last Name</Label>
                    <Input id="lastName" value={lastName} onChange={e => setLastName(e.target.value)} className="bg-background/50" />
                  </div>
                </div>

                <div className="pt-4 flex justify-end">
                  <Button 
                    type="submit" 
                    className="min-w-[150px] shadow-lg shadow-primary/20"
                    disabled={updateProfileMutation.isPending}
                  >
                    {updateProfileMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                    Save Changes
                  </Button>
                </div>
              </CardContent>
            </form>
          </Card>

        </div>
      </main>
    </div>
  );
}
