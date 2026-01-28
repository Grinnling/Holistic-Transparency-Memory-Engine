# Remote Desktop Access Build Requirements

## Project Overview
Set up browser-based remote desktop access to home development workstation using Apache Guacamole + TigerVNC for full desktop access from work via any web browser.

## System Requirements

### Hardware Requirements
- **Home Workstation**: Already setup (development sandbox environment)
- **Network**: Broadband internet with decent upload speed (5+ Mbps recommended)
- **Router**: Port forwarding capability or UPnP support

### Software Prerequisites
- **Operating System**: Ubuntu/Linux (already installed)
- **Docker**: For containerized Guacamole deployment
- **Existing Services**: Development sandbox, containers, VS Codium, Claude Code

## Component Architecture

```
[Work Browser] → [HTTPS/SSL] → [Nginx Reverse Proxy] → [Guacamole Container] → [VNC Server] → [Virtual Desktop]
                                                      ↓
                                                [MySQL Database]
```

## Required Software Stack

### Core Services
1. **Apache Guacamole** (Docker containers)
   - `guacamole/guacamole` - Web application
   - `guacamole/guacd` - Guacamole daemon
   - `mysql:8.0` - Database backend

2. **TigerVNC Server**
   - Virtual desktop server
   - User session management
   - Display server for remote access

3. **Nginx** 
   - Reverse proxy
   - SSL termination
   - Security headers

4. **SSL Certificate**
   - Let's Encrypt (free option)
   - Self-signed certificate (backup option)

## Security Features

### Authentication Options
- [x] Built-in Guacamole user database
- [ ] Two-factor authentication (optional enhancement)
- [ ] IP address restrictions (optional enhancement)

### Network Security
- [x] HTTPS/SSL encryption
- [x] Reverse proxy configuration
- [x] Non-standard port options
- [ ] Fail2ban integration (optional enhancement)

## Installation Requirements

### Package Dependencies
```bash
# System packages needed
- tigervnc-standalone-server
- nginx
- certbot (for Let's Encrypt SSL)
- docker.io
- docker-compose
```

### Network Configuration
- **Port 443**: HTTPS access (external facing)
- **Port 5901**: VNC server (internal only)
- **Port 8080**: Guacamole (internal only)
- **Port 3306**: MySQL (internal only)

### Router/Firewall Setup
- Port forwarding: External 443 → Internal 443
- Internal firewall: Allow Docker bridge networks
- Optional: Restrict source IP addresses

## File Structure Requirements

```
/opt/remote-desktop/
├── docker-compose.yml          # Main container orchestration
├── nginx/
│   ├── nginx.conf             # Reverse proxy configuration
│   └── ssl/                   # SSL certificates
├── guacamole/
│   ├── init/                  # Database initialization
│   └── data/                  # Persistent data
└── scripts/
    ├── setup.sh               # Installation script
    ├── start-vnc.sh          # VNC server startup
    └── backup.sh             # Backup configuration
```

## Configuration Requirements

### VNC Server Configuration
- Display: `:1` (port 5901)
- Resolution: 1920x1080 (adjustable)
- Color depth: 24-bit
- Password authentication
- Auto-start on boot

### Guacamole Configuration
- MySQL database backend
- VNC connection profile
- User authentication
- Session recording (optional)

### Nginx Configuration
- SSL certificate handling
- Proxy headers
- WebSocket support for Guacamole
- Security headers (HSTS, etc.)

## Performance Considerations

### Resource Requirements
- **RAM**: 2GB minimum for VNC desktop session
- **CPU**: Minimal overhead for VNC/Guacamole
- **Network**: Upload bandwidth impacts responsiveness
- **Storage**: ~500MB for containers + desktop session space

### Optimization Options
- VNC compression settings
- Display resolution adjustment
- Connection quality settings
- Session timeout configuration

## Backup & Maintenance

### What to Backup
- Guacamole database (user accounts, connections)
- SSL certificates
- Configuration files
- VNC server configuration

### Maintenance Tasks
- SSL certificate renewal (automated with certbot)
- Database backups
- Log rotation
- Security updates

## Testing Requirements

### Functionality Testing
- [ ] VNC server starts and accepts connections
- [ ] Guacamole web interface accessible
- [ ] SSL certificate valid and working
- [ ] Full desktop session accessible via browser
- [ ] Terminal access works (Claude Code compatibility)
- [ ] Development tools accessible (VS Codium, containers)

### Security Testing
- [ ] HTTPS enforced (no HTTP access)
- [ ] Authentication required
- [ ] Failed login attempts handled properly
- [ ] Network ports properly isolated

### Performance Testing
- [ ] Responsive desktop interaction
- [ ] Multiple terminal windows work smoothly
- [ ] File operations perform adequately
- [ ] Development workflow maintains usability

## Success Criteria

### Primary Goals
- [x] Full Ubuntu desktop accessible via any web browser
- [x] All development tools work normally (VS Codium, terminals, containers)
- [x] Claude Code functions properly in browser-accessed terminals
- [x] Secure HTTPS access from work network
- [x] No additional software required on work computer

### Quality Metrics
- Desktop response time < 200ms on local network
- Usable performance over work internet connection
- Secure authentication preventing unauthorized access
- Reliable connection stability for work sessions

## Deployment Notes

### Installation Order
1. Install system packages
2. Configure TigerVNC server
3. Set up Docker containers (Guacamole + MySQL)
4. Configure Nginx reverse proxy
5. Obtain and install SSL certificate
6. Configure network/firewall
7. Test functionality

### Rollback Plan
- VNC server can be stopped/disabled
- Docker containers can be stopped/removed
- Nginx configuration can be reverted
- Port forwarding can be disabled
- No permanent system changes required

## Documentation Requirements

### User Documentation
- Connection instructions for work access
- Troubleshooting common issues
- Performance optimization tips
- Security best practices

### Technical Documentation
- Installation procedure
- Configuration file explanations
- Backup/restore procedures
- Update and maintenance procedures