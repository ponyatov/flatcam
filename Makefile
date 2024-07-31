# var
MODULE = $(notdir $(CURDIR))
OS     = $(shell uname -s)

# dirs
CWD = $(CURDIR)

# tool
CURL = curl -L -o
# venv
PY   = $(CWD)/bin/python3
PIP  = $(CWD)/bin/pip3
# system-wide
# PY   = /usr/bin/python3
# PIP  = /usr/bin/pip3

# src
P += $(wildcard *.py)

# all
.PHONY: all
all: $(PY) $(MODULE).py
	$^

# format
.PHONY: format
format: tmp/format_py
tmp/format_py: $(P)
	echo format: $?

# Install on Ubuntu(-like) systems

# Install dependencies system-wide (including python modules)
install_dependencies:
	sudo -H ./setup_ubuntu.sh

USER_ID = $(shell id -u)

LOCAL_PATH = $(shell pwd)
LOCAL_APPS_PATH = ~/.local/share/applications
ASSEST_PATH = assets/linux

INSTALL_PATH = /usr/share/flatcam-beta
APPS_PATH = /usr/share/applications

MIN_PY3_MINOR_VERSION := 6
PY3_MINOR_VERSION := $(shell python3 --version | cut -d'.' -f2)

compare = $(shell if [ $(1) -gt $(2) ] ; then echo gt ; else echo lt ; fi)

ifneq ($(call compare,$(PY3_MINOR_VERSION),$(MIN_PY3_MINOR_VERSION)),gt)
    $(info  Current python version is 3.$(PY3_MINOR_VERSION))
    $(error    You must have at least 3.$(MIN_PY3_MINOR_VERSION) installed)
endif

# install

ifeq ($(OS), Linux)
include /etc/os-release
endif

.PHONY: install update

# first install
install: $(PIP) install_$(OS)
	$(MAKE) update

# update packages & libs
update: $(PIP) update_$(OS)
	# venv
	$(PIP) install -U -r requirements.${ID}

.PHONY: install_$(OS) update_$(OS)
install_$(OS):
update_$(OS):
# sudo apt update
	sudo apt install -uy `cat apt.dev apt.${ID}`

# venv
$(CWD)/bin/python3 $(CWD)/bin/pip3: /usr/bin/python3
	$< -m venv .
	$(CWD)/bin/pip3 install -U pip
# system-wide
/usr/bin/python3 /usr/bin/pip3:
	sudo apt install -uy python3 python3-pip

install.desktop:
ifeq ($(USER_ID), 0)
	@ echo "Installing it system-wide"
	cp -rf $(LOCAL_PATH) $(INSTALL_PATH)
	@ sed -i "s|python_script_path=.*|python_script_path=$(INSTALL_PATH)|g" $(INSTALL_PATH)/assets/linux/flatcam-beta
	ln -sf $(INSTALL_PATH)/assets/linux/flatcam-beta /usr/local/bin
	cp -f $(ASSEST_PATH)/flatcam-beta.desktop $(APPS_PATH)
	@ sed -i "s|Exec=.*|Exec=$(INSTALL_PATH)/$(ASSEST_PATH)/flatcam-beta|g" $(APPS_PATH)/flatcam-beta.desktop
	@ sed -i "s|Icon=.*|Icon=$(INSTALL_PATH)/$(ASSEST_PATH)/icon.png|g" $(APPS_PATH)/flatcam-beta.desktop
else
	@ echo "Installing locally for $(USER) only"
	cp -f $(ASSEST_PATH)/flatcam-beta.desktop $(LOCAL_APPS_PATH)
	@ sed -i "s|Exec=.*|Exec=$(LOCAL_PATH)/$(ASSEST_PATH)/flatcam-beta|g" $(LOCAL_APPS_PATH)/flatcam-beta.desktop
	@ sed -i "s|Icon=.*|Icon=$(LOCAL_PATH)/$(ASSEST_PATH)/icon.png|g" $(LOCAL_APPS_PATH)/flatcam-beta.desktop
endif

remove.desktop:
ifeq ($(USER_ID), 0)
	@ echo "Uninstalling it system-wide"
	rm -rf $(INSTALL_PATH)
	rm -f /usr/local/bin/flatcam-beta
	rm -r $(APPS_PATH)/flatcam-beta.desktop
else
	@ echo "Uninstalling only for $(USER) user"
	rm -f $(LOCAL_APPS_PATH)/flatcam-beta.desktop
endif
