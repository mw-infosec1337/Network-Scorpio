🦂 Network Scorpio
A cross-platform terminal network toolkit — scan, secure, troubleshoot, and understand your network in one place. 🌐⚡

Python Platform License

Network Scorpio — by Mohamed W Abdelwahed
© Mohamed W Abdelwahed

✨ What is Network Scorpio?
Network Scorpio 🦂 is an interactive CLI tool that gives you a sysadmin-style control panel for your machine and LAN — no GUI required.

From a single menu you can:

📊 Inspect your connection and public IP
🔍 Discover every device on your network
🛡️ Monitor live traffic like a host firewall
🧰 Troubleshoot a user’s PC like IT support
🚀 Run an internet speed test
🌐 Change DNS settings
Built for Kali, Ubuntu, Windows 11, macOS, and more. 🖥️📱

🎯 Features
1️⃣ Network info 📡
Interface, Wi-Fi SSID, link speed, MTU
Gateway, DNS servers, local IPs
Public WAN IP, city, ISP, timezone
2️⃣ Scan your network 🔎
Fast LAN discovery (nmap or parallel ping)
Structured host cards per device:
🏷️ Highlighted device name (e.g. MacBookPro, kali)
🖥️ Device type (Apple Mac, Router, Linux, etc.)
🏭 Manufacturer from MAC (OUI)
⏱️ Latency, open services (HTTP, SSH, AirPlay, …)
3️⃣ Network Security 🛡️
Host firewall view — what’s open right now
Live connections with brand names (Google, Cursor, Microsoft, …)
Inbound / outbound peers with highlighted app & website names
⚠️ Suspicious activity alerts only when something looks risky
Optional remediation (stop process, firewall hints)
4️⃣ Troubleshoot User 🧰
Pick target by IP, hostname, or quick LAN scan
Ping, gateway, DNS, internet, common ports
Plain-English verdict for IT support
5️⃣ Internet speed test 🚀
Download / upload / ping via speedtest-cli
6️⃣ Configure DNS 🌐
Apply DNS on Linux (NetworkManager), macOS, Windows

Menu	LAN scan	Security monitor
(screenshot)
(screenshot)
(screenshot)
🌍 Supported platforms
OS	Support
🐧 Linux
Ubuntu, Debian, Kali, Fedora, Arch, openSUSE, Alpine, Mint, Manjaro, RHEL, WSL, …
🪟 Windows
10 / 11 / Server
🍎 macOS
10.14 Mojave and newer
🐡 BSD
FreeBSD, OpenBSD, NetBSD
Python 3.9+ required 🐍

📦 Requirements
Python packages (auto-installed on first run)
speedtest-cli>=2.1.3
colorama>=0.4.6
psutil>=5.9.0
Optional (recommended) 🔧
nmap — faster discovery & port scans (offered at first launch via your package manager)
🚀 Quick start
1. Clone the repo 📥
git clone https://github.com/YOUR_USERNAME/network-scorpio.git
cd network-scorpio
2. Run the tool ▶️
python3 scorpio.py
On first launch you’ll see the animated Network Scorpio banner 🦂✨ and a prompt to install dependencies (Y/N).

3. Best results on Linux 🐧
For full socket/process details (especially Network Security):

sudo python3 scorpio.py
📋 Menu
Options
  1  Network info
  2  Scan your network
  3  Network Security
  4  Troubleshoot User
  5  Internet speed test
  6  Configure DNS
  7  Exit
After most tasks: press Esc to return to the menu or type exit to quit. 👋

📁 Project structure
network-scorpio/
├── scorpio.py          # Main application
├── requirements.txt    # Python dependencies
└── README.md           # You are here 📖
⚙️ How it works (short)
Feature	Tech
🔍 LAN scan
nmap -sn or parallel ICMP ping
🏷️ Device names
PTR DNS, MAC OUI, hostname patterns
🌐 Brand detection
Hostname rules + optional IP org lookup
🛡️ Security
psutil live sockets + heuristics
🚀 Speed test
speedtest-cli
🌐 DNS
nmcli / networksetup / PowerShell
⚠️ Disclaimer
Network Scorpio is for legitimate use on networks and systems you own or are authorized to administer. 🛡️

Do not use it to attack or monitor networks without permission.
Firewall / process actions may need root or Administrator.
Speed tests and IP lookups use third-party services.
You are responsible for how you use this tool. ⚖️

🤝 Contributing
Pull requests welcome! 🎉

Fork the repo 🍴
Create a branch (git checkout -b feature/amazing-feature) 🌿
Commit your changes (git commit -m 'Add amazing feature') 💾
Push (git push origin feature/amazing-feature) 🚀
Open a Pull Request ✨
📄 License
MIT License — see LICENSE for details. 📜
(Add a LICENSE file if you haven’t yet.)

👤 Author
Mohamed W Abdelwahed

GitHub: @mw-infosec1337
Tool: Network Scorpio 🦂
If this project helps you, consider giving it a ⭐ on GitHub!

🦂 Network Scorpio — see your network clearly.
Made with ❤️ by Mohamed W Abdelwahed


