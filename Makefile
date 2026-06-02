INSTALL_DIR ?= $(HOME)/.local/bin

.PHONY: install uninstall demo run

install:
	mkdir -p $(INSTALL_DIR)
	ln -sf $(CURDIR)/fordtracker $(INSTALL_DIR)/fordtracker
	@echo "Installed → $(INSTALL_DIR)/fordtracker"
	@echo "Make sure $(INSTALL_DIR) is in your PATH."

uninstall:
	rm -f $(INSTALL_DIR)/fordtracker
	@echo "Removed $(INSTALL_DIR)/fordtracker"

demo:
	./fordtracker --demo

run:
	./fordtracker
