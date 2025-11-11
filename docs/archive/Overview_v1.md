# Family and Friends E Ink Message Board Project

## 📌 Project Goal
Create a **family and friends physical message board** using a color E Ink display and Raspberry Pi that everyone in the "Stream" can remotely update with messages and images.
### Setup
I'll build each StreamScene Frame using the hardware resources below and ship them to family and friends. They will then need a simple way to setup by the StreamScene Frame by:
- Making an account on the StreamScene web app
- Plugging the StreamScene Frame into a wall adapter for power
- Connecting the StreamScene Frame to the WiFi via mobile phone
- Registering their device to their StreamScene account

### Streams
Once setup is complete, users will be able to create their own Streams (multiple are allowed) or subscribe to other Streams.

Owners and subscribers to Streams will have the ability to post to Streams

Users can decide which stream they want to be displayed on their StreamScene Frame, or if they want a loop showing the last post of selected Streams

All content displayed on the StreamScene Frame will show who posted, date and time, the Stream name. This content should be minimally displayed with the text of being the main object.

Owners of Streams can change settings of Streams to:
- Allow for text only, allow for pictures only or allow for both
- If the Stream is public and searchable or if the Stream is private and requires owner approval
- If only the last post of a Stream is show, or if a loop of posts are shown

---

## 🖥️ Hardware Resources

- **Raspberry Pi Zero 2 WH**
  - Compact & low-power single board computer
  - Integrated Wi-Fi
- **Color E Ink Display**
  - Example options: Pimoroni Inky Impression 7.3" (800x480) or Waveshare 7.5" color panel
  - Compatible with Raspberry Pi GPIO
- **SanDisk Ultra Android MicroSDXC UHS-I Card 64GB**
  - Class 10, A1, U1, up to 140MB/s read speed
  - Perfect for Raspberry Pi OS, message/image storage
  - Includes SD adapter

---

## 🛠️ Homelab Resources

- **Proxmox**  
  - Hypervisor running on your homelab hardware
  - http://192.168.1.30
- **LXC Container**  for StreamScene
  - Lightweight container for running backend services or messaging board logic
- **Authentik in LXC 108**  
  - Identity and authentication provider for secure family logins
  - http://192.168.1.108:9000
- **Nginx Proxy Manager in LXC 104**  
  - Reverse proxy and SSL/TLS management
  - http://192.168.1.104:81
- **Domain: dataandstories.com**  
  - Public-facing domain to host remote update portals or endpoints

---

## 🌐 Tech Stack

- **Raspberry Pi Zero 2 WH**:
  - OS: Raspberry Pi OS (installed on microSD card)
- **Python Reflex**:
  - Full stack web app
- **E Ink Display Libraries**:
  - For controlling the color display and rendering content
- **Homelab Integration**:
  - Backend web service runs in LXC container on Proxmox
  - Authentik container provides secure logins for family members
  - Nginx Proxy Manager container provides public access and SSL
  - Frontend/remote update site hosted at `https://dataandstories.com`

---

## 🔑 Key Features

- Remote message and image posting from anywhere
- Images are preprocessed on the StreamScene server for compatible display 
- Family-wide secure login using Authentik
- All messages displayed on color E Ink screen, powered by Raspberry Pi
- Low-power operation, always-on updates
- Expandable for future features (weather, events)

---
