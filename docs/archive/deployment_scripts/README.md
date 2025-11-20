# Deployment Scripts Archive

**Archived:** November 20, 2025
**Reason:** One-off debugging scripts no longer needed after WiFi setup completion

## Contents

These scripts were created for ad-hoc debugging and troubleshooting during the WiFi setup development phase (Nov 16-18, 2025). They have been superseded by production deployment tools.

### Archived Scripts

1. **check_devices.py** (Nov 16)
   - Script for checking device registration status
   - Replaced by device management web UI

2. **check_portal.sh** (Nov 17)
   - Quick portal accessibility check
   - Debugging tool for captive portal issues

3. **clean_pi.sh** (Nov 16)
   - Cleanup script for resetting Pi state between tests
   - Used during manual deployment iteration

4. **fix_pi.sh** (Nov 16)
   - Emergency fix script for common Pi deployment issues
   - Addressed specific bugs that are now fixed in main code

5. **fix_portal_permissions.sh** (Nov 17)
   - Script to fix portal server port binding permissions
   - Issue resolved by moving portal to port 8080

6. **investigate_pi.sh** (Nov 16)
   - Diagnostic script for Pi network state investigation
   - Used during WiFi hotspot debugging

7. **pi_diagnostic.sh** (Nov 18)
   - Comprehensive diagnostic script for Pi debugging
   - Most comprehensive of the debugging tools
   - Checks network state, service status, logs, configs

8. **configure_pi_production.sh** (Nov 16)
   - Early attempt at Pi configuration automation
   - Replaced by build_sd_image.sh and proper first-boot provisioning

## Production Replacements

These archived scripts have been replaced by:

- **build_sd_image.sh** - Production SD card image builder
- **deploy_to_pi.sh** - Device deployment and testing utility
- **client/provision.sh** - First-boot provisioning script (runs once on new SD card)
- **Systemd service** - Automatic management of hotspot/client modes

## Historical Value

These scripts document the iterative debugging process and are kept for:
- Historical reference of issues encountered
- Understanding the evolution of the deployment system
- Potential reuse of diagnostic techniques in future debugging
