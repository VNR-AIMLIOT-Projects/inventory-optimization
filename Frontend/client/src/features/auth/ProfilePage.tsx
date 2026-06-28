import { Sidebar } from "@/components/common/Sidebar";
import { Header } from "@/components/common/Header";
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
import { Loader2, ShieldAlert, KeyRound } from "lucide-react";

export default function ProfilePage() {
  const { isCollapsed } = useSidebar();
  const { user } = useAuth();
  const { toast } = useToast();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName]   = useState("");

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
      toast({ title: "Profile saved", description: "Your name has been updated." });
    },
    onError: (err: Error) => {
      toast({ title: "Update failed", description: err.message, variant: "destructive" });
    },
  });

  const displayInitial = (user?.firstName?.[0] || user?.username?.[0] || "?").toUpperCase();
  const displayName    = user?.firstName
    ? `${user.firstName}${user.lastName ? " " + user.lastName : ""}`
    : user?.username?.split("@")[0] ?? "User";

  return (
    <div className="flex min-h-dvh bg-background text-foreground font-sans selection:bg-primary/20">
      <Sidebar />
      <main
        className={cn(
          "flex-1 flex flex-col relative z-10 transition-all duration-300 ease-spring",
          isCollapsed ? "lg:ml-[5.5rem]" : "lg:ml-[17rem]",
        )}
      >
        <Header title="Profile" />

        <div className="px-6 pb-20 pt-8 max-w-2xl mx-auto w-full animate-fade-in-up">
          
          {/* ── Avatar hero ── */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5 mb-10">
            <div className="w-20 h-20 rounded-2xl bg-primary/15 border-2 border-primary/25 flex items-center justify-center shrink-0">
              <span className="font-display font-bold text-4xl text-primary">{displayInitial}</span>
            </div>
            <div>
              <h1 className="font-display font-bold text-3xl text-foreground capitalize">{displayName}</h1>
              <p className="text-muted-foreground text-sm mt-1">{user?.username}</p>
              <span className="inline-block mt-2 text-[10px] font-semibold text-primary bg-primary/10 border border-primary/20 px-2 py-0.5 rounded-full uppercase tracking-wide">
                Active account
              </span>
            </div>
          </div>

          {/* ── Personal information ── */}
          <section aria-labelledby="section-personal">
            <div className="mb-5">
              <h2 id="section-personal" className="font-display font-semibold text-lg text-foreground">Personal information</h2>
              <p className="text-sm text-muted-foreground mt-0.5">Update your display name.</p>
            </div>

            <form onSubmit={(e) => { e.preventDefault(); updateProfileMutation.mutate({ firstName, lastName }); }}>
              <div className="bg-card border border-border rounded-2xl p-6 shadow-amber space-y-5">
                {/* Email (read-only) */}
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium text-foreground">Email address</Label>
                  <Input
                    readOnly
                    value={user?.username ?? ""}
                    className="bg-muted/50 text-muted-foreground cursor-not-allowed border-border/50 h-11"
                  />
                  <p className="text-xs text-muted-foreground">Email cannot be changed after account creation.</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="firstName" className="text-sm font-medium text-foreground">First name</Label>
                    <Input
                      id="firstName"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      className="h-11 bg-background border-border focus:border-primary transition-colors"
                      placeholder="Alex"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="lastName" className="text-sm font-medium text-foreground">Last name</Label>
                    <Input
                      id="lastName"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      className="h-11 bg-background border-border focus:border-primary transition-colors"
                      placeholder="Rivera"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <Button
                    type="submit"
                    disabled={updateProfileMutation.isPending}
                    className="bg-primary text-primary-foreground font-semibold h-10 px-5 rounded-xl hover:brightness-105 active:scale-[0.97] transition-all shadow-amber"
                  >
                    {updateProfileMutation.isPending && <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />}
                    Save changes
                  </Button>
                </div>
              </div>
            </form>
          </section>

          {/* ── Security section ── */}
          <section aria-labelledby="section-security" className="mt-8">
            <div className="mb-5">
              <h2 id="section-security" className="font-display font-semibold text-lg text-foreground">Security</h2>
              <p className="text-sm text-muted-foreground mt-0.5">Manage your account security settings.</p>
            </div>
            <div className="bg-card border border-border rounded-2xl p-6 shadow-amber flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center shrink-0">
                <KeyRound className="w-4.5 h-4.5 text-muted-foreground" />
              </div>
              <div className="flex-1">
                <p className="font-medium text-foreground text-sm">Password</p>
                <p className="text-xs text-muted-foreground mt-0.5">Change your login password.</p>
              </div>
              <button
                type="button"
                className="text-sm font-medium text-primary hover:text-primary/80 transition-colors"
                onClick={() => toast({ title: "Coming soon", description: "Password change will be available shortly." })}
              >
                Change
              </button>
            </div>
          </section>

          {/* ── Danger zone ── */}
          <section aria-labelledby="section-danger" className="mt-8">
            <div className="mb-5">
              <h2 id="section-danger" className="font-display font-semibold text-lg text-foreground">Danger zone</h2>
            </div>
            <div className="bg-destructive/5 border border-destructive/25 rounded-2xl p-6 flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-destructive/10 flex items-center justify-center shrink-0">
                <ShieldAlert className="w-4.5 h-4.5 text-destructive" />
              </div>
              <div className="flex-1">
                <p className="font-medium text-foreground text-sm">Delete account</p>
                <p className="text-xs text-muted-foreground mt-0.5">Permanently remove your account and all associated data.</p>
              </div>
              <button
                type="button"
                className="text-sm font-medium text-destructive hover:text-destructive/80 transition-colors"
                onClick={() => toast({ title: "Contact support", description: "Please reach out to delete your account.", variant: "destructive" })}
              >
                Delete
              </button>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
