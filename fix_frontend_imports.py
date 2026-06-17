import os
import glob

replacements = {
    '@/components/Header': '@/components/common/Header',
    '@/components/Sidebar': '@/components/common/Sidebar',
    '@/components/StageNav': '@/components/common/StageNav',
    '@/components/ThemeToggle': '@/components/common/ThemeToggle',
    '@/components/PageCopilot': '@/features/copilot/PageCopilot',
    '@/components/DecisionCard': '@/features/deployment/components/DecisionCard',
    '@/pages/Stage1Data': '@/features/demand/Stage1Data',
    '@/pages/ModifyDemand': '@/features/demand/ModifyDemand',
    '@/pages/PreviewDemand': '@/features/demand/PreviewDemand',
    '@/pages/DataUpload': '@/features/demand/DataUpload',
    '@/pages/Stage2Training': '@/features/training/Stage2Training',
    '@/pages/AgentMonitor': '@/features/training/AgentMonitor',
    '@/pages/Stage3Deployment': '@/features/deployment/Stage3Deployment',
    '@/pages/DeploymentDashboard': '@/features/deployment/DeploymentDashboard',
    '@/pages/AuthPage': '@/features/auth/AuthPage',
    '@/pages/ProfilePage': '@/features/auth/ProfilePage',
}

files = glob.glob('Frontend/client/src/**/*.tsx', recursive=True) + glob.glob('Frontend/client/src/**/*.ts', recursive=True)

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements.items():
        new_content = new_content.replace(old, new)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")
