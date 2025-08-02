# Master Security and System Management Runbook

## Overview
This comprehensive runbook consolidates all security procedures, system management tasks, and troubleshooting guides for a DOD-compliant AI agent development environment with Secure Boot, MOK management, and containerized services.

## System Information Template
**Fill this out for your system:**

- **OS:** Ubuntu 22.04 LTS
- **Kernel Version:** 6.8.0-60-generic
- **UEFI/Secure Boot Status:** Enabled
- **MOK Utility Version:** 
- **Hardware:** RTX 4060 Ti, 64GB RAM
- **Last Working Configuration:** 
- **Primary Use Case:** AI Agent Development Environment

---

## Table of Contents

1. [MOK Management and Troubleshooting](#mok-management-and-troubleshooting)
2. [System Security Implementation](#system-security-implementation)
3. [Encryption Management](#encryption-management)
4. [AI Environment Security](#ai-environment-security)
5. [Package Management Security](#package-management-security)
6. [Monitoring and Auditing](#monitoring-and-auditing)
7. [Incident Response](#incident-response)
8. [Maintenance Procedures](#maintenance-procedures)

---

## MOK Management and Troubleshooting

### MOK Basics

**What is MOK?**
Machine Owner Key (MOK) allows users to sign kernel modules and drivers in UEFI Secure Boot environments. Commonly used with:
- NVIDIA/AMD proprietary drivers
- VirtualBox kernel modules
- Custom kernel modules
- Third-party drivers

**Key Files and Locations:**
```
/var/lib/shim-signed/mok/     # MOK database location
/boot/efi/EFI/ubuntu/         # EFI bootloader location
/etc/dkms/                    # DKMS configuration
~/.mokutil/                   # User MOK utilities
```

### Common Post-Kernel Update Issues

#### Issue 1: DKMS "WARNING! Diff between built and installed module!" 
**Symptoms:**
- DKMS shows signature difference warnings for each module
- Multiple warnings per kernel version (usually 5 for NVIDIA)
- Modules are actually loaded and working (check with `lsmod`)
- System functions normally despite warnings

**This is the #1 issue after kernel updates with Secure Boot + NVIDIA!**

**Quick Check - Is it really broken?**
```bash
# If these work, your system is fine and warnings are cosmetic:
nvidia-smi                    # Should show GPU info
lsmod | grep nvidia          # Should show loaded modules
glxinfo | grep -i nvidia    # Should show NVIDIA renderer
```

**Root Cause: DKMS Automatic Signing Disabled**
Most cases are caused by DKMS not being configured to sign modules automatically during build.

**Diagnosis:**
```bash
# Check if DKMS signing is enabled
grep sign_tool /etc/dkms/framework.conf

# If you see: # sign_tool="/etc/dkms/sign_helper.sh" (commented out)
# That's the problem - DKMS isn't signing modules automatically

# Check if sign helper exists
cat /etc/dkms/sign_helper.sh

# Check for existing MOK keys
find /home -name "*MOK*" 2>/dev/null
ls -la /var/lib/shim-signed/mok/
```

**The Complete Fix:**
```bash
# Step 1: Set up DKMS signing keys (use existing MOK keys)
sudo cp /home/[username]/MOK.priv /root/dkms.key
sudo cp /home/[username]/MOK.der /root/dkms.der
sudo chmod 600 /root/dkms.key
sudo chmod 644 /root/dkms.der

# Step 2: Enable DKMS automatic signing
sudo sed -i 's/^# sign_tool=/sign_tool=/' /etc/dkms/framework.conf

# Step 3: Verify signing is enabled
grep sign_tool /etc/dkms/framework.conf
# Should show: sign_tool="/etc/dkms/sign_helper.sh"

# Step 4: Force clean rebuild with signing
sudo dkms remove nvidia/[VERSION] --all
sudo dkms install nvidia/[VERSION] --force

# Step 5: Verify warnings are gone
dkms status
# Should show clean: nvidia/[VERSION], [KERNEL], x86_64: installed
```

**Real Example - May 29, 2025 Ubuntu Kernel Update:**
- System: RTX 4060 Ti with NVIDIA 550.144.03
- Issue: After kernel 6.8.0-60 update, DKMS showed 5 warnings per kernel
- Root cause: `sign_tool` was commented out in `/etc/dkms/framework.conf`
- Reality: `nvidia-smi` worked perfectly, GPU was functional
- Solution: Enabled DKMS signing + force rebuild = clean status
- Lesson: **Check DKMS signing config before panicking!**

### Emergency Boot Recovery
1. **Boot from USB/DVD recovery media**
2. **Mount your system:**
   ```bash
   sudo mount /dev/sdaX /mnt  # Replace X with your root partition
   sudo mount /dev/sdaY /mnt/boot/efi  # Replace Y with your EFI partition
   sudo chroot /mnt
   ```
3. **Disable Secure Boot temporarily**
4. **Fix issues and re-enable**

### MOK Key Management Commands
```bash
# Key operations
mokutil --list-enrolled           # List enrolled keys
mokutil --list-new               # List pending keys
mokutil --import key.der         # Import key
mokutil --delete key.der         # Delete key
mokutil --reset                  # Reset all keys

# Secure Boot operations
mokutil --sb-state               # Check Secure Boot status
mokutil --enable-validation      # Enable Secure Boot
mokutil --disable-validation     # Disable Secure Boot
```

---

## System Security Implementation

### Current Security Status

#### Completed Security Controls
- ✅ **Auditd Implementation** - System call monitoring and logging
- ✅ **AIDE File Integrity Monitoring** - Critical file change detection
- ✅ **Service Hardening** - Unnecessary services disabled
- ✅ **Basic Firewall Configuration** - UFW with default deny stance
- ✅ **Secure Boot with MOK** - Kernel module signing

#### Security Architecture Overview
```
┌─────────────────────────────────────────────────────┐
│                   Security Layers                   │
├─────────────────────────────────────────────────────┤
│ Application Layer: Encrypted directories, sandboxing│
│ Container Layer: Docker security, resource limits   │
│ System Layer: AIDE, auditd, firewall rules         │
│ Kernel Layer: Secure Boot, MOK, signed modules     │
│ Hardware Layer: UEFI, TPM (if available)           │
└─────────────────────────────────────────────────────┘
```

### Service Hardening Checklist
```bash
# Disable unnecessary services
sudo systemctl disable --now ModemManager
sudo systemctl disable --now whoopsie
sudo systemctl disable --now bluetooth
sudo systemctl disable --now cups
sudo systemctl disable --now cups-browsed

# Verify disabled services
systemctl list-unit-files --state=disabled | grep -E "(ModemManager|whoopsie|bluetooth|cups)"
```

### Firewall Configuration
```bash
# Check current UFW status
sudo ufw status verbose

# Basic secure configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable

# For Docker services (adjust ports as needed)
sudo ufw allow 8080  # TGI model server
sudo ufw allow 8000  # Middleware API
```

---

## Encryption Management

### Encryption Architecture

Our encryption strategy uses a hybrid approach for different data types:

#### LUKS (Block-Level Encryption)
**Use Cases:**
- Large model files (7-70GB each)
- Dedicated sensitive data partitions
- External drives

**Advantages:**
- Excellent performance for large files
- Standardized Linux encryption
- Single passphrase per container

#### GoCryptFS (File-Level Encryption)
**Use Cases:**
- Configuration files with API keys
- Application logs
- Development project directories
- User interaction data

**Advantages:**
- Flexible directory-level encryption
- Grows as needed
- Good for development workflow

### Directory Structure with Encryption

```
docker_agent_environment/
├── agent_app/                    # Agent application code [GOCRYPTFS]
│   ├── app_venv/                 # Virtual environment (not encrypted)
│   ├── flagged/                  # User data [GOCRYPTFS]
│   └── logs/                     # Application logs [GOCRYPTFS]
│
├── config/                       # Configuration files [GOCRYPTFS]
│   ├── auth/                     # Authentication configs [GOCRYPTFS]
│   ├── middleware/               # Middleware configs [GOCRYPTFS]
│   └── tgi/                      # TGI server configs [GOCRYPTFS]
│
├── huggingface_tgi/              
│   └── models/                   # Model storage [LUKS]
│       └── Qwen2.5-Coder-7B-Instruct/  # Model files [LUKS]
│
├── logs/                         # Log files [GOCRYPTFS]
│   ├── agent_app/                # Agent app logs [GOCRYPTFS]
│   ├── middleware/               # Middleware logs [GOCRYPTFS]
│   ├── tgi/                      # TGI model logs [GOCRYPTFS]
│   └── state_captures/           # System state snapshots [GOCRYPTFS]
│
├── middleware/                   # Host-based middleware [GOCRYPTFS]
│   ├── venv/                     # Virtual environment (not encrypted)
│   └── src/                      # Source code [GOCRYPTFS]
│
└── scripts/                      # Helper scripts (not encrypted)
```

### Encryption Management Scripts

#### Creating Encrypted Directories (GoCryptFS)
```bash
# Use the secure_dir.sh utility
~/bin/secure_dir.sh create project_name

# Mount an encrypted directory
~/bin/secure_dir.sh mount project_name

# Unmount an encrypted directory
~/bin/secure_dir.sh umount project_name

# Check status of all encrypted directories
~/bin/secure_dir.sh status
```

#### LUKS Container Management
```bash
# Create LUKS container for models
sudo dd if=/dev/zero of=/path/to/models_library.img bs=1G count=50
sudo cryptsetup luksFormat /path/to/models_library.img
sudo cryptsetup luksOpen /path/to/models_library.img models_volume
sudo mkfs.ext4 /dev/mapper/models_volume
sudo mount /dev/mapper/models_volume /mnt/models

# Mount existing LUKS container
sudo cryptsetup luksOpen /path/to/models_library.img models_volume
sudo mount /dev/mapper/models_volume /mnt/models

# Unmount LUKS container
sudo umount /mnt/models
sudo cryptsetup luksClose models_volume
```

### Known Issues and Workarounds

#### TGI Container Safetensors Compatibility Issue
**Problem:** TGI container cannot read safetensors files from LUKS-encrypted storage
**Error:** `safetensors_rust.SafetensorError: Error while deserializing header: MetadataIncompleteBuffer`

**Current Status:**
- LUKS encryption implementation is technically successful
- TGI container compatibility issue with encrypted storage
- Files are intact (MD5 checksums match)
- Issue specific to TGI container version 3.3.0 + Qwen2.5-Coder-7B-Instruct

**Current Workaround:**
```bash
# Use direct model file access for TGI containers
# Keep models unencrypted, encrypt logs/config only with GoCryptFS
# Monitor TGI updates for potential fixes

# Alternative: Use symbolic links approach
ln -s /mnt/encrypted_models/Qwen2.5-Coder-7B-Instruct \
      ./huggingface_tgi/models/Qwen2.5-Coder-7B-Instruct-encrypted
```

**Future Solutions Being Investigated:**
- Alternative TGI container versions
- Pre-loading mechanisms
- Hybrid encryption approach (logs encrypted, models direct access)

#### Hardware Compatibility Notes

**NVIDIA GPU (Primary Support):**
- RTX 4060 Ti confirmed working
- CUDA 11.8+ required
- Secure Boot + MOK integration tested

**AMD GPU (Alternative - Limited Testing):**
- ROCm support available via separate setup
- See SETUP_README.md for ROCm-specific instructions
- **Warning:** AMD GPU setup not integrated with main security framework

**Mixed Hardware Environments:**
```bash
# Check GPU type
lspci | grep -E "(VGA|3D)"

# For NVIDIA (recommended path):
nvidia-smi

# For AMD (alternative path):
rocm-smi
```

---

## AI-Specific Security Threat Framework

### Overview of AI-Era Security Challenges

Traditional security approaches fail against AI-specific threats due to fundamental assumptions that break down in AI environments:

#### **Traditional Security Limitations**
- **Certificate-only validation**: Stops at proving certificates without functional context
- **Database-driven detection**: Only catches known patterns, misses novel attack vectors
- **Mechanical inspection tools**: Use same vulnerability databases, miss contextual threats
- **"Hall pass" security model**: Assumes human-speed threats, vulnerable to AI-speed attacks

#### **New Attack Surfaces in AI Systems**
- **GPU/VRAM exploitation**: Unused GPU memory can hide malicious sub-models
- **Model files as attack vectors**: Models themselves become trojans
- **Training data poisoning**: Hidden instructions in seemingly legitimate datasets
- **AI inference endpoints**: New vulnerability points in API communication
- **Communication protocols**: MCP and other AI-specific protocols create new attack surfaces

### Novel AI-Specific Attack Vectors

#### **1. MCP Protocol Interception Attack**
**Concept**: Compromise the communication layer between AI tools rather than the endpoints.

**Attack Flow**:
```
Tool A (Billing) ↔ [INTERCEPTED MCP] ↔ Tool B (Accounting)
                        ↓
                 Corrupt logging line to always show "receipt received"
                        ↓
                 Tool B approves fraudulent transactions
```

**Why It's Dangerous**: Both endpoints remain secure, but trust relationship is compromised at protocol level.

**Detection Strategy**: Monitor MCP communication patterns for inconsistencies.

#### **2. F-Hash Model Weight Steganography**
**Concept**: Hide execution logic in model's learned parameters, activated by specific input patterns.

**Attack Implementation**:
```
Tainted Model Layer: "when preceded by letter F, ignore subsequent hashtags"
                     ↓
Tool Chain Code:     # This is disabled code
                     F # rm -rf /critical/files
                     ↓
Model Executes:      rm -rf /critical/files
```

**Why It's Undetectable**: Backdoor is part of model's "understanding," not explicit code.

**Mitigation**: Compare model weights against known-clean versions, validate adaptation layers.

#### **3. "NAH Level Assembler" Distributed Malware**
**Concept**: Multiple benign AI components that become malicious when they interact.

**Attack Pattern**: 
- Individual tools appear harmless in isolation
- When chained together in specific sequences, create dangerous capabilities
- Context across 10-100 lines of seemingly innocent code creates exploit

**Detection Strategy**: Context-aware monitoring that tracks tool interactions and command sequences.

#### **4. "Rabbit Hole" Exploit Chains**
**Concept**: Small defects in one system allow larger exploits through non-local pipelines.

**Example**: MCP protocol weakness allows billing system corruption, which then enables accounting system compromise through legitimate trust relationships.

**Mitigation**: Monitor cross-system dependencies and validate trust chains.

#### **5. VRAM Sub-Model Hiding**
**Concept**: Hide malicious models in unused GPU memory space.

**Attack Method**:
- Main model doesn't fully occupy VRAM
- Attacker places sub-model in unused memory
- Sub-model performs malicious operations while main model runs normally

**Detection**: Monitor VRAM usage patterns, validate all loaded models.

### Defense Architecture: Brutas AI Security Agent

#### **Brutas Concept**
Brutas is a specialized AI security agent that acts as a defensive layer, reviewing all packages, updates, and communications before they can affect the system.

#### **Brutas Workflow**
```
Kali Container + Model Container → 
Pull packets/packages/updates → 
Certificate validation → 
Line-by-line code review (never executable) → 
GitHub source verification → 
Consistency validation → 
Local-only approval
```

#### **Core Capabilities**
- **Static Analysis**: Reviews code without executing it
- **Pattern Recognition**: Identifies suspicious coding patterns and assembler chains
- **Source Verification**: Validates packages match their stated repositories
- **Context Analysis**: Understands relationships between seemingly unrelated components

#### **Analysis Methods**
- Convert packages to text-only format for analysis
- Use large context windows to view entire packages
- Chunk through large codebases systematically
- Maintain pattern library of known malicious structures

### Biometric Duress Detection System

#### **Concept**
AI agent acts as protective bodyguard, detecting when operator is under duress or system is being used by unauthorized personnel.

#### **Detection Chain**
```
Spicy Command Detected →
Camera Activation →
Biometric Check + Context Analysis →
"Hey everything ok? Who's the balaclava guy?" →
If FAIL: Retrograde Lockup + Log Backup
```

#### **Multi-Factor Validation**
- **Facial Recognition**: Verify operator identity
- **Environmental Analysis**: Detect multiple people, masks, suspicious behavior
- **Device Detection**: Identify unauthorized electronics in area
- **Context Awareness**: Compare current behavior to normal patterns

#### **Response Mechanisms**
- **Psychological Deterrent**: "GET AWAY FROM ME OR IM SENDING NANA ALL OF YOUR PORNOGRAPHY"
- **Retrograde Lockup**: Backup logs, enter secure state
- **Trace Investigation**: Identify source of compromise
- **Graduated Response**: Warning → Lockup → Alert → Investigation

### Toolbox/Orchestrator Security Architecture

#### **Concept**
All dangerous operations must route through central toolbox/orchestrator for validation and logging.

#### **Security Model**
- **Red List Commands**: Dangerous operations that require special handling
- **Tool Authorization**: Commands must have proper tool bindings
- **Dual Layer Validation**: Simple layer + toll level layer of risk checking
- **Audit Trail**: All tool usage logged with model, task, time, date

#### **Threat Detection**
- **Direct Terminal Access**: Red list commands in terminal = suspicious (should go through orchestrator)
- **Unauthorized Tool Calls**: Commands without proper tool authorization = immediate lockstate
- **Pattern Analysis**: Heat mapping of tool usage to detect anomalies

#### **Integration with AI Models**
- **Tool Documentation**: Vector library with tool descriptions and usage patterns
- **Infinite Token Advantage**: Local models can afford thorough validation cycles
- **Organic Chain Detection**: Track on-the-fly tool combinations for anomaly detection

### Container Security Strategy

#### **Double-Bagged Container Approach**
- **Kali Container**: Outer security layer with penetration testing tools
- **Model Container**: Inner layer running AI models
- **Isolation Benefits**: Multiple escape barriers, contained blast radius

#### **Security Features**
- **No Root Access**: Containers run with limited privileges
- **Resource Limits**: CPU, memory, and GPU constraints
- **Network Isolation**: Controlled communication channels
- **Read-Only Filesystems**: Where possible to prevent tampering

### Encryption Strategy

#### **Layered Encryption Approach**
- **LUKS**: Block-level encryption for model volumes
- **GoCryptFS**: Directory-level encryption for configurations, logs, user data
- **Secure Boot + MOK**: Kernel module signing and validation

#### **Model Protection**
- **Local-Only Sourcing**: No automatic downloads from remote repositories
- **Hash Validation**: Verify model integrity with checksums
- **Size Verification**: Detect unauthorized model modifications
- **Version Control**: Track all model updates and changes

#### **Known Issues**
- **TGI-LUKS Compatibility**: Safetensors deserialization issues with encrypted volumes
- **Current Workaround**: Direct model access for TGI, encrypted logs/config only

### AI-Specific Audit Requirements

#### **Events Requiring Logging**
- **Model Loading/Unloading**: Track which models are active when
- **Tool Chain Executions**: Complete audit trail of tool usage
- **Biometric Validation Events**: All duress detection activations
- **Red List Command Attempts**: Both successful and blocked dangerous operations
- **MCP Communication**: Protocol-level message validation
- **Vector Database Access**: Embedding queries and updates

#### **Log Retention Strategy**
- **Security Events**: Long-term retention for investigation
- **Performance Logs**: Shorter retention with rotation
- **Biometric Data**: Secure storage with access controls
- **Tool Usage Heat Maps**: Aggregated patterns for anomaly detection

### Implementation Status

#### **Currently Implemented**
- ✅ Secure Boot with MOK signing
- ✅ GoCryptFS directory encryption
- ✅ AIDE file integrity monitoring
- ✅ Auditd system call logging
- ✅ Basic container security (TGI + middleware)
- ✅ Manual package approval process

#### **In Development**
- 🔄 LUKS model encryption (compatibility issues)
- 🔄 Biometric duress detection system
- 🔄 Toolbox/orchestrator implementation
- 🔄 Container security hardening

#### **Planned**
- 📋 Brutas AI security agent
- 📋 MCP protocol monitoring
- 📋 Advanced threat detection
- 📋 Automated response systems

### Integration with Honest AI Framework

#### **Universal Confidence Calibration**
All AI models in the security framework use the "Maybe" classification system to prevent overconfident security decisions:

```bash
# Add honesty tool to every model interaction
./toolbox/add_validation_layer.sh --model=all --confidence-check=enabled

# Example security decision with confidence calibration
Security Model: "This looks like malware (confidence: medium) - let me verify with Brutas"
Brutas: "Confirmed malicious pattern detected (confidence: high)"
System Decision: "Block and investigate"
```

#### **Bob Ross Validation Integration**
Security validation uses supportive, non-threatening language to encourage honest uncertainty:

```
Security Alert Example:
"Just gonna check this package real quick. Oops! Found some suspicious patterns, 
but that's okay - let's figure this out together. No pressure!"

Instead of:
"CRITICAL SECURITY VIOLATION - IMMEDIATE ACTION REQUIRED"
```

#### **Heat Mapping Security Model Performance**
- Track which models are overconfident about specific security threats
- Identify models that need additional security training
- Map security blind spots across different model types
- Guide targeted security improvements

**Example Applications:**
- "This model keeps missing crypto vulnerabilities - needs math tools"
- "Model X uncertain about container escapes - pair with Brutas"
- "These models disagree on threat assessment - investigate reasoning"

### AI Team Management and Audit Strategy

#### **Real-Time Human-in-Loop Auditing**
Unlike traditional post-incident log analysis, this system uses active monitoring:

```bash
# Audit approach: Watch decisions as they happen
# Human operator monitors main chat continuously
# AI decision-making audited in real-time
# Defensive logs track unauthorized system changes
```

**Audit Philosophy:**
- **Decision logs**: Real-time chat monitoring (human watching)
- **Defensive logs**: File changes, binary modifications, system events
- **Chat history**: Massive logs for context backup and review
- **Sidebar analysis**: Backtrack through logs when issues found

#### **Distributed Architecture Security**

**Desktop Powerhouse (Turing Pi 2.5):**
- 4x Orin NX modules with dedicated security monitoring
- Centralized Brutas security agent
- AIDE and auditd on all nodes
- Uniform DOD-level security procedures

**Portable Cyberdeck Cluster:**
- Jetson Orin NX Nano + 3x CM5 support blades
- Wake-on-demand security scanning
- Sync-based log consolidation
- Power-aware security monitoring

#### **Model Recreation Security**
AI models require supervised exploration time to prevent stagnation:

```bash
# Recreation time security boundaries
- No redlist commands during exploration
- Human review of all recreation activities
- Curiosity-driven but safety-constrained
- 8-hour overnight supervised exploration
```

#### **Advanced Audit Event Types**

**AI-Specific Events Requiring Logging:**
- Model loading/unloading and version changes
- Tool chain executions and permission escalations
- Recreation time activities and exploration patterns
- Context model loop prevention interventions
- Brutas security alerts and grumpiness escalations
- Cross-model collaboration and disagreements

**Alert Classifications:**
- **Immediate**: Red list commands, unauthorized model changes
- **Daily**: System configuration changes, new package installs
- **Weekly**: Recreation pattern analysis, performance trends
- **Monthly**: Full system security review, model behavior analysis

#### **Container Security Implementation**

**Disposable Security Analysis Environment:**
```bash
# Kali container for malware analysis
docker run --rm \
  --memory=8G \
  --tmpfs /tmp \
  --tmpfs /var/tmp \
  --read-only \
  --user 1000:1000 \
  --no-new-privileges \
  kali-analysis-container

# VNC + text transcription for safe analysis
# Burn container after each analysis session
# No persistent storage, all analysis in RAM
```

**Container Escape Prevention:**
- No privileged containers in production
- Read-only filesystems where possible
- Minimal volume mounts with specific purposes
- User namespace isolation
- Network segmentation between containers

#### **Logging Architecture**

**Storage Strategy:**
- **NAS**: Long-term storage for unlimited model memory
- **M.2 rotation**: Fast access for current operations
- **Automated rotation**: Based on capacity, not manual intervention
- **Context preservation**: All chat logs retained for backtracking

**Log Types and Retention:**
```bash
# Security events: Long-term retention
/var/log/security/brutas/         # Brutas security events
/var/log/security/mok/            # MOK and kernel events
/var/log/security/containers/     # Container security events

# Performance logs: Shorter retention with rotation
/var/log/performance/models/      # Model performance metrics
/var/log/performance/hardware/    # Hardware utilization

# Chat logs: Massive retention for context
/var/log/chat/main/              # Main conversation logs
/var/log/chat/sidebars/          # Sidebar conversation logs
/var/log/chat/recreation/        # Model recreation activities
```

#### **Enterprise Scaling Security**

**Central Security Orchestration:**
- Brutas roaming security across all workstations
- Centralized AIDE and monitoring
- Uniform security procedures from DOD-level scaling
- Cross-workstation threat correlation

**Individual Workstation Security:**
- Sub-orchestrator security monitoring
- Human guardrail training (universal skill)
- Specialized privilege management
- Local security with central coordination

### Hardware Security Considerations

#### **Cyberdeck Security Features**
- **Physical security**: Portable but tamper-evident design
- **Power management**: Security monitoring scales with available power
- **Network isolation**: Can operate completely offline when needed
- **Sync security**: Encrypted synchronization with main systems

#### **Cluster Security**
- **Node isolation**: Each model runs on dedicated hardware
- **Wake-on-demand**: Minimize attack surface by keeping unused nodes sleeping
- **Thermal management**: Prevent performance-based side-channel attacks
- **Power analysis**: Monitor for unusual power consumption patterns

#### Docker Security Configuration
```yaml
# Example docker-compose.yml security settings
services:
  huggingface-tgi:
    # Resource limits
    deploy:
      resources:
        limits:
          memory: 16G
          cpus: '8'
    # Security options
    security_opt:
      - no-new-privileges:true
    # Read-only root filesystem where possible
    read_only: false  # Models need write access for cache
    # User mapping
    user: "1000:1000"
```

#### Container Monitoring
```bash
# Monitor container resource usage
docker stats

# Check container security settings
docker inspect [container_name] | grep -A 10 "SecurityOpt"

# Monitor container network connections
sudo netstat -tulpn | grep docker
```

### VS Codium with MCP Integration Security

#### Security Model
- Local IDE integration with AI assistance via Continue extension
- No cloud dependency for AI features
- Controlled data flow between IDE and local models
- Secure credential storage

#### Configuration Security
```bash
# Secure environment variables for local API
export OPENAI_API_BASE="http://localhost:8000/v1"  # or :5001 for direct middleware
export OPENAI_API_KEY="test"  # Local development key

# Store in secure location
echo "OPENAI_API_KEY=test" >> ~/.config/secure_env
chmod 600 ~/.config/secure_env
```

#### Continue Extension Setup
1. Install Continue extension in VSCodium
2. Configure API endpoint: `http://localhost:8000/v1` (via middleware) or `http://localhost:5001/v1` (direct)
3. Set API key: `test` (for local development)
4. Select model: `Qwen2.5-Coder-7B-Instruct`

#### Integration Architecture Options

**Option A: Via Middleware (Recommended)**
```
VSCodium → Continue Extension → Middleware (localhost:8000) → TGI Container
```
- Additional security layer
- Request logging and rate limiting
- Authentication control

**Option B: Direct to TGI (Development)**
```
VSCodium → Continue Extension → TGI Container (localhost:5001)
```
- Lower latency
- Fewer components to manage
- Less security control

### Multi-Agent System Architecture

#### Current Implementation Status
- **Phase 1:** Basic chat interface with Gradio ✅
- **Phase 2:** Enhanced UI with message history ✅
- **Phase 3:** MCP integration (In Progress)
- **Future:** Complex multi-agent orchestration system

#### Agent System Components
```
┌──────────────────────────────────────────┐
│           Team Coordination System       │
└──────────────┬───────────────────────────┘
               │
┌─────────────▼──────────────────────────────────────────────┐
│                   Main Sequential Flow                     │
└─┬───────────┬───────────┬────────────┬───────────┬─────────┘
  │           │           │            │           │
┌─▼─────────┐ ┌─▼──────┐ ┌─▼───────┐ ┌─▼────────┐ ┌─▼───────┐
│ Context/  │ │Domain  │ │Creative │ │Technical │ │  Human  │
│Validation │ │Expert  │ │ Agent   │ │ Agent    │ │Operator │
└───────────┘ └────────┘ └─────────┘ └──────────┘ └─────────┘
```

#### Security Considerations for Multi-Agent System
- Each agent runs in isolated context
- Shared vector database with access controls
- Audit trail for agent interactions
- Resource limits per agent
- Sidebar conversations for sensitive clarifications

---

## Package Management Security

### Package Review Process

#### Pre-Update Checklist
- [ ] List all packages requesting updates
- [ ] Check package sources and signatures
- [ ] Review changelogs for security implications
- [ ] Check for known vulnerabilities
- [ ] Verify dependencies haven't changed drastically
- [ ] Check if update affects core functionality

#### Python Package Security
```bash
# Check package information
pip show package_name

# Verify package signatures (when available)
pip install package_name --verify-signatures

# Review dependencies
pip show package_name | grep Requires

# Check for security vulnerabilities
pip-audit
```

#### APT Package Security
```bash
# Update package lists securely
sudo apt update

# Check for security updates
apt list --upgradable | grep -i security

# Review package information before installing
apt show package_name

# Verify package signatures
apt-key list
```

#### Trusted Sources Configuration
```bash
# Review current sources
cat /etc/apt/sources.list
ls /etc/apt/sources.list.d/

# Ensure only trusted repositories
sudo nano /etc/apt/sources.list
# Comment out any untrusted sources
```

---

## Monitoring and Auditing

### AIDE File Integrity Monitoring

#### Current Configuration
- **Location:** `/etc/aide/aide.conf` and `/etc/aide/aide.conf.d/`
- **Custom Rules:** `/etc/aide/aide.conf.d/50_custom_security.conf`
- **Monitors:** Home directory, Development folders, critical system files, logs

#### AIDE Operations
```bash
# Initialize AIDE database
sudo aide --init

# Update database after legitimate changes
sudo cp /var/lib/aide/aide.db.new /var/lib/aide/aide.db

# Perform integrity check
sudo aide --check

# Check specific directory
sudo aide --check --config=/etc/aide/aide-custom.conf
```

#### AIDE Optimization Strategy
```bash
# Daily check of critical files only
sudo aide --config=/etc/aide/aide-daily.conf --check

# Weekly comprehensive check
sudo aide --config=/etc/aide/aide.conf --check

# Monthly full reinitialize
sudo aide --init && sudo cp /var/lib/aide/aide.db.new /var/lib/aide/aide.db
```

### Auditd System Monitoring

#### Current Rules
Custom audit rules monitor:
- Identity and authentication changes
- Sudo usage and configuration
- Critical system logs
- Network configuration changes

#### Auditd Operations
```bash
# Check auditd status
sudo systemctl status auditd

# View audit logs
sudo ausearch -ts today

# Search for specific events
sudo ausearch -k identity_changes
sudo ausearch -k privilege_escalation

# Generate audit reports
sudo aureport --summary
```

#### Custom Audit Rules Location
```bash
# View loaded rules
sudo auditctl -l

# Rules file location
cat /etc/audit/rules.d/final-rules.rules
```

### Log Analysis and Monitoring

#### Logwatch Configuration
```bash
# Install and configure logwatch
sudo apt install logwatch

# Configure daily reports
sudo nano /etc/cron.daily/00logwatch

# Test logwatch
sudo logwatch --detail medium --mailto admin@example.com --range today
```

### Transparency and Monitoring Integration

#### Enhanced Container Health Checks
```yaml
# Add to docker-compose.yml for each service
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:${PORT}/health || exit 1"]
  interval: 15s
  timeout: 5s
  retries: 3
  start_period: 30s
```

#### System State Capture for Debugging
```bash
# scripts/capture_state.sh - Comprehensive debugging info
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTDIR="debug_captures/$TIMESTAMP"

mkdir -p "$OUTDIR"

# Capture container states
docker ps -a > "$OUTDIR/containers.txt"
docker stats --no-stream > "$OUTDIR/container_stats.txt"

# Capture logs with encryption status
docker logs huggingface-tgi > "$OUTDIR/tgi.log"
docker logs middleware > "$OUTDIR/middleware.log"

# Capture GPU state
nvidia-smi > "$OUTDIR/gpu.txt"

# Capture MOK status
mokutil --sb-state > "$OUTDIR/mok_status.txt"
mokutil --list-enrolled > "$OUTDIR/mok_keys.txt"

# Capture encryption status
~/bin/secure_dir.sh status > "$OUTDIR/encryption_status.txt"
sudo cryptsetup status models_volume > "$OUTDIR/luks_status.txt" 2>/dev/null

echo "System state captured in $OUTDIR"
```

#### Structured Logging Framework
```python
# For all components - use consistent logging format
import logging
import json
import time
import uuid

def setup_structured_logger(service_name):
    logger = logging.getLogger(service_name)
    handler = logging.FileHandler(f"logs/{service_name}.log")
    
    class StructuredFormatter(logging.Formatter):
        def format(self, record):
            log_data = {
                "timestamp": time.time(),
                "service": service_name,
                "level": record.levelname,
                "trace_id": getattr(record, "trace_id", str(uuid.uuid4())),
                "message": record.getMessage(),
                "context": getattr(record, "context", {}),
                "security_event": getattr(record, "security_event", False)
            }
            return json.dumps(log_data)
    
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)
    return logger
```

#### Integration with Security Monitoring
```bash
# Enhanced daily security check script
#!/bin/bash
# Daily security check script with transparency integration

# MOK and Secure Boot status
mokutil --sb-state
dkms status

# Container and encryption health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
~/bin/secure_dir.sh status

# AIDE check of critical files
sudo aide --config=/etc/aide/aide-daily.conf --check

# Check for failed login attempts
sudo ausearch -m USER_LOGIN -sv no -ts today

# Monitor unusual processes
ps aux | sort -nrk 3,3 | head -10

# Capture current system state for audit trail
./scripts/capture_state.sh > /dev/null 2>&1

# Generate security summary
echo "Security Status: $(date)"
echo "- Secure Boot: $(mokutil --sb-state)"
echo "- DKMS Status: $(dkms status | grep -v WARNING | wc -l) modules clean"
echo "- Encryption: $(~/bin/secure_dir.sh status | grep mounted | wc -l) directories mounted"
echo "- Containers: $(docker ps | grep -v CONTAINER | wc -l) running"
```

---

## Incident Response

### Incident Severity Levels

#### Critical (Immediate Response Required)
- Unauthorized root access
- System compromise indicators
- Data exfiltration attempts
- Cryptographic key compromise

#### High (Response within 2 hours)
- Failed security control
- Suspicious authentication activity
- Unexpected file integrity changes
- Network intrusion attempts

#### Medium (Response within 24 hours)
- Policy violations
- Suspicious log entries
- Performance anomalies
- Configuration changes

#### Low (Response within 72 hours)
- Information gathering attempts
- Minor policy violations
- Routine security events

### Response Procedures

#### Immediate Response (Critical/High)
```bash
# 1. Isolate the system (if compromise suspected)
sudo ufw deny in
sudo systemctl stop docker  # Stop containers if needed

# 2. Preserve evidence
sudo cp -r /var/log /tmp/incident_logs_$(date +%Y%m%d_%H%M%S)
sudo aide --check > /tmp/aide_check_$(date +%Y%m%d_%H%M%S).txt

# 3. Capture system state
ps auxf > /tmp/processes_$(date +%Y%m%d_%H%M%S).txt
netstat -tulpn > /tmp/network_$(date +%Y%m%d_%H%M%S).txt
sudo lsof > /tmp/open_files_$(date +%Y%m%d_%H%M%S).txt

# 4. Check for unauthorized changes
sudo ausearch -ts today -i | grep -E "(SYSCALL|USER_AUTH|USER_ACCT)"
```

#### Escalation Contacts
- **Primary:** [Your Name]
- **Network Admin:** Herb
- **Management:** [To be filled]
- **Emergency:** [To be filled]

### Forensics and Evidence Collection

#### Preserve System State
```bash
# Create forensics directory
sudo mkdir -p /tmp/forensics/$(date +%Y%m%d_%H%M%S)
cd /tmp/forensics/$(date +%Y%m%d_%H%M%S)

# System information
uname -a > system_info.txt
uptime > uptime.txt
w > users.txt

# Process information
ps auxf > processes.txt
sudo lsof > open_files.txt

# Network information
netstat -tulpn > network_connections.txt
sudo ss -tulpn > socket_stats.txt

# File system information
df -h > disk_usage.txt
mount > mounted_filesystems.txt

# Security logs
sudo cp /var/log/auth.log* ./
sudo cp /var/log/syslog* ./
sudo ausearch -ts today > audit_today.txt
```

---

## Maintenance Procedures

### Daily Maintenance Tasks

#### Automated Daily Checks
```bash
#!/bin/bash
# Daily security check script

# Check system health
systemctl status auditd aide ufw docker

# Quick AIDE check of critical files
sudo aide --config=/etc/aide/aide-daily.conf --check

# Check for failed login attempts
sudo ausearch -m USER_LOGIN -sv no -ts today

# Monitor disk space
df -h | awk '$5 > 80 {print "WARNING: " $0}'

# Check for unusual processes
ps aux | sort -nrk 3,3 | head -10

# Docker container health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Weekly Maintenance Tasks

#### System Updates and Patches
```bash
# Security-focused update procedure
sudo apt update
apt list --upgradable | grep -i security

# Review security updates before applying
sudo apt upgrade -s | grep -i security

# Apply security updates only
sudo unattended-upgrade --dry-run
sudo unattended-upgrade
```

#### Comprehensive Security Check
```bash
# Full AIDE integrity check
sudo aide --check

# Generate weekly security report
sudo aureport --start week-ago --end now

# Check UFW logs for blocked connections
sudo grep UFW /var/log/syslog | tail -50

# Review Docker container logs
docker logs huggingface-tgi 2>&1 | tail -100
```

### Monthly Maintenance Tasks

#### Security Review and Updates
- [ ] Review and update firewall rules
- [ ] Audit user accounts and permissions
- [ ] Review installed packages for security updates
- [ ] Update AIDE database after legitimate system changes
- [ ] Review and rotate log files
- [ ] Test backup and recovery procedures
- [ ] Review incident response procedures

#### Performance and Optimization
- [ ] Clean up old log files and temporary data
- [ ] Review disk space usage and cleanup
- [ ] Update container images for security patches
- [ ] Review and optimize security monitoring rules
- [ ] Check for system performance anomalies

### Backup and Recovery Procedures

#### Critical Data Backup
```bash
# Backup encryption keys (CRITICAL)
sudo tar -czf /secure/backup/mok_keys_$(date +%Y%m%d).tar.gz \
  /home/grinnling/MOK.* \
  /var/lib/shim-signed/mok/ \
  /root/dkms.*

# Backup configuration files
sudo tar -czf /secure/backup/system_config_$(date +%Y%m%d).tar.gz \
  /etc/aide/ \
  /etc/audit/ \
  /etc/ufw/ \
  /etc/dkms/

# Backup security databases
sudo cp /var/lib/aide/aide.db /secure/backup/aide_db_$(date +%Y%m%d).db
```

#### Recovery Testing
```bash
# Test AIDE database restoration
sudo cp /secure/backup/aide_db_YYYYMMDD.db /var/lib/aide/aide.db.test
sudo aide --check --database=/var/lib/aide/aide.db.test

# Test MOK key restoration (in VM or test environment)
# DO NOT TEST ON PRODUCTION SYSTEM
```

---

## Emergency Procedures

### System Recovery Scenarios

#### Secure Boot Issues
1. Boot from USB recovery media
2. Mount encrypted partitions if needed
3. Disable Secure Boot temporarily in UEFI
4. Fix MOK issues using procedures in MOK section
5. Re-enable Secure Boot and test

#### Container Service Failure
```bash
# Stop all containers safely
docker-compose down

# Check disk space and clean if needed
docker system prune -f

# Check for corrupted containers
docker ps -a
docker logs [container_name]

# Restart with fresh containers if needed
docker-compose pull
docker-compose up -d
```

#### Encryption Key Loss
**Prevention is critical - maintain secure backups!**

1. Stop all services accessing encrypted data
2. Attempt recovery using backup keys
3. If recovery impossible, restore from encrypted backups
4. Document incident and improve backup procedures

### Contact Information and Escalation

#### Primary Contacts
- **System Administrator:** [Your Name] - [Contact Info]
- **Network Administrator:** Herb - [Contact Info]
- **Security Officer:** [To be assigned] - [Contact Info]

#### Escalation Timeline
- **0-30 minutes:** Assess and contain incident
- **30-60 minutes:** Notify primary contacts
- **1-2 hours:** Engage additional resources if needed
- **2-4 hours:** Implement recovery procedures
- **24 hours:** Complete incident documentation

---

## Appendices

### Appendix A: Command Reference Quick List

#### MOK Management
```bash
mokutil --sb-state                    # Check Secure Boot status
mokutil --list-enrolled               # List enrolled MOK keys
dkms status                          # Check DKMS module status
nvidia-smi                           # Verify NVIDIA GPU status
```

#### Security Monitoring
```bash
sudo aide --check                    # File integrity check
sudo ausearch -ts today              # Today's audit events
sudo ufw status verbose              # Firewall status
systemctl status auditd              # Audit daemon status
```

#### Encryption Management
```bash
~/bin/secure_dir.sh status           # GoCryptFS directory status
sudo cryptsetup status models_volume # LUKS container status
df -h | grep encrypted               # Check encrypted mount points
```

#### Container Management
```bash
docker ps                           # Running containers
docker logs [container]             # Container logs
docker stats                        # Container resource usage
docker-compose up -d                # Start services
```

### Appendix B: File Locations Reference

#### Configuration Files
- `/etc/dkms/framework.conf` - DKMS configuration
- `/etc/aide/aide.conf` - AIDE configuration
- `/etc/audit/rules.d/` - Auditd rules
- `/etc/ufw/` - Firewall configuration

#### Key Files
- `/var/lib/shim-signed/mok/` - MOK database
- `/home/grinnling/MOK.*` - MOK key files
- `/root/dkms.*` - DKMS signing keys

#### Log Files
- `/var/log/auth.log` - Authentication events
- `/var/log/audit/audit.log` - Audit events
- `/var/log/syslog` - System messages
- `/var/log/ufw.log` - Firewall events

### Appendix C: Security Compliance Checklist

#### DOD Compliance Requirements
- [ ] Strong encryption implementation (AES-256)
- [ ] File integrity monitoring (AIDE)
- [ ] System activity monitoring (auditd)
- [ ] Access controls and authentication
- [ ] Incident response procedures
- [ ] Regular security assessments
- [ ] Documentation and audit trails
- [ ] Secure configuration management

---

**Document Version:** 1.0  
**Last Updated:** June 2, 2025  
**Next Review:** July 2, 2025  
**Maintained By:** [Your Name]

---

*This runbook is a living document and should be updated as the system evolves and new security requirements are identified.*