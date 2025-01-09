from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QMessageBox, QGroupBox, QFormLayout, QLineEdit,
                             QListWidget, QListWidgetItem, QCheckBox, QTextEdit,
                             QLabel)
from botocore.exceptions import ClientError

from finch.common import s3_session, center_window, resource_path, StringUtils
from finch.error import show_error_dialog


class CORSWindow(QWidget):
    """
    CORS Window to manage CORS configurations for passed bucket name.
    """
    def __init__(self, bucket_name):
        super().__init__()
        self.bucket_name = bucket_name
        self.setWindowTitle(f"CORS Configurations - {bucket_name}")
        self.resize(600, 400)
        center_window(self)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # List of CORS Rules
        self.rules_list = QListWidget()
        self.rules_list.itemClicked.connect(self.show_rule_details)
        self.rules_list.currentRowChanged.connect(self.show_rule_details)
        layout.addWidget(self.rules_list)

        # Rule Editor Group
        rule_group = QGroupBox("Rule Details")
        rule_layout = QFormLayout()
        rule_group.setLayout(rule_layout)

        # Set the form layout to expand fields horizontally
        rule_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.allowed_origins_input = QTextEdit()
        self.allowed_origins_input.setMaximumHeight(80)
        rule_layout.addRow("Allowed Origins:", self.allowed_origins_input)
        help_label = QLabel("Enter * or http://example.com\nOne origin per line")
        help_label.setStyleSheet("QLabel { font-size: 11px; font-style: italic; color: #666; }")
        rule_layout.addRow("", help_label)

        # Methods as checkboxes
        methods_group = QWidget()
        methods_layout = QHBoxLayout()
        methods_group.setLayout(methods_layout)
        self.method_checkboxes = {}
        for method in ["GET", "PUT", "POST", "DELETE", "HEAD"]:
            checkbox = QCheckBox(method)
            self.method_checkboxes[method] = checkbox
            methods_layout.addWidget(checkbox)
        rule_layout.addRow("Allowed Methods:", methods_group)

        self.allowed_headers_input = QTextEdit()
        self.allowed_headers_input.setMaximumHeight(80)
        rule_layout.addRow("Allowed Headers:", self.allowed_headers_input)
        help_label = QLabel("Enter * or specific headers\nOne header per line")
        help_label.setStyleSheet("QLabel { font-size: 11px; font-style: italic; color: #666; }")
        rule_layout.addRow("", help_label)

        self.expose_headers_input = QTextEdit()
        self.expose_headers_input.setMaximumHeight(80)
        rule_layout.addRow("Expose Headers:", self.expose_headers_input)
        help_label = QLabel("Enter headers to expose\nOne header per line")
        help_label.setStyleSheet("QLabel { font-size: 11px; font-style: italic; color: #666; }")
        rule_layout.addRow("", help_label)

        self.max_age_input = QLineEdit()
        rule_layout.addRow("Max Age (seconds):", self.max_age_input)
        help_label = QLabel("Enter maximum age in seconds")
        help_label.setStyleSheet("QLabel { font-size: 11px; font-style: italic; color: #666; }")
        rule_layout.addRow("", help_label)

        # Add buttons to form
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_widget.setLayout(buttons_layout)

        self.save_rule_button = QPushButton("Save Changes")
        self.save_rule_button.setIcon(QIcon(resource_path("img/save.svg")))
        self.save_rule_button.clicked.connect(self.save_rule)
        self.save_rule_button.setEnabled(False)
        
        self.delete_rule_button = QPushButton("Delete Rule")
        self.delete_rule_button.setIcon(QIcon(resource_path("img/trash.svg")))
        self.delete_rule_button.clicked.connect(self.delete_rule)
        self.delete_rule_button.setEnabled(False)

        buttons_layout.addWidget(self.save_rule_button)
        buttons_layout.addWidget(self.delete_rule_button)
        buttons_layout.setAlignment(Qt.AlignLeft)
        rule_layout.addRow("", buttons_widget)

        layout.addWidget(rule_group)

        # Bottom buttons
        button_layout = QHBoxLayout()
        self.add_rule_button = QPushButton("Add New Rule")
        self.add_rule_button.setIcon(QIcon(resource_path("img/plus.svg")))
        self.add_rule_button.clicked.connect(self.add_new_rule)
        
        self.apply_button = QPushButton("Apply CORS Rules")
        self.apply_button.setIcon(QIcon(resource_path("img/save.svg")))
        self.apply_button.clicked.connect(self.apply_cors)

        button_layout.addWidget(self.add_rule_button)
        button_layout.addWidget(self.apply_button)
        button_layout.setAlignment(Qt.AlignRight)
        
        layout.addLayout(button_layout)

        # Start with form disabled
        self._enable_form(False)
        
        # Load existing CORS configuration
        self.load_cors_config()

    def load_cors_config(self):
        """Load existing CORS configuration for the bucket"""
        try:
            response = s3_session.resource.meta.client.get_bucket_cors(Bucket=self.bucket_name)
            rules = response.get('CORSRules', [])
            
            for rule in rules:
                item = QListWidgetItem(self._format_rule_display(
                    rule['AllowedMethods'],
                    rule['AllowedOrigins']
                ))
                item.setData(Qt.UserRole, rule)
                self.rules_list.addItem(item)
            
            # Select first rule if any exist
            if self.rules_list.count() > 0:
                self.rules_list.setCurrentRow(0)

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchCORSConfiguration':
                # No CORS configuration exists yet
                pass
            else:
                show_error_dialog(str(e))

    def show_rule_details(self, item_or_row):
        """Show details of selected rule"""
        # Convert row number to item if needed
        if isinstance(item_or_row, int):
            item = self.rules_list.item(item_or_row)
        else:
            item = item_or_row

        if not item:
            self._enable_form(False)
            return

        self._enable_form(True)
        rule = item.data(Qt.UserRole)
        self.allowed_origins_input.setPlainText("\n".join(rule.get('AllowedOrigins', [])))
        
        # Set method checkboxes
        allowed_methods = rule.get('AllowedMethods', [])
        for method, checkbox in self.method_checkboxes.items():
            checkbox.setChecked(method in allowed_methods)
            
        self.allowed_headers_input.setPlainText("\n".join(rule.get('AllowedHeaders', [])))
        self.expose_headers_input.setPlainText("\n".join(rule.get('ExposeHeaders', [])))
        self.max_age_input.setText(str(rule.get('MaxAgeSeconds', '')))
        self.save_rule_button.setEnabled(False)  # Disable save button when loading rule
        self.delete_rule_button.setEnabled(True)

    def add_new_rule(self):
        """Add empty rule to the list"""
        # Save existing changes if any
        if self.save_rule_button.isEnabled():
            if not self._get_rule_from_form():  # Returns None if validation fails
                return  # Don't add new rule if current rule has validation errors
            self.save_rule()

        # Then add new rule
        item = QListWidgetItem("New Rule")
        item.setData(Qt.UserRole, {"AllowedOrigins": [], "AllowedMethods": []})
        self.rules_list.addItem(item)
        self.rules_list.setCurrentItem(item)
        self._clear_form()
        self._enable_form(True)
        self.save_rule_button.setEnabled(True)
        self.delete_rule_button.setEnabled(True)

    def _format_rule_display(self, methods, origins):
        """Format CORS rules to display in the list"""
        methods_text = StringUtils.format_list_with_conjunction(methods)
        origins_text = StringUtils.format_list_with_conjunction(['anywhere' if o == '*' else o for o in origins])
        return f"{methods_text} on {origins_text}"

    def save_rule(self):
        """Save current form data to selected rule"""
        current_item = self.rules_list.currentItem()
        if current_item:
            updated_rule = self._get_rule_from_form()
            if updated_rule:
                current_item.setData(Qt.UserRole, updated_rule)
                current_item.setText(self._format_rule_display(
                    updated_rule['AllowedMethods'],
                    updated_rule['AllowedOrigins']
                ))
                self.save_rule_button.setEnabled(False)

    def _on_form_changed(self):
        """Enable save button when form content changes"""
        if self.rules_list.currentItem():
            current_rule = self.rules_list.currentItem().data(Qt.UserRole)
            new_rule = self._get_rule_from_form(validate=False)
            if new_rule:
                self.save_rule_button.setEnabled(current_rule != new_rule)

    def _get_rule_from_form(self, validate=True):
        """Get rule dict from form fields"""
        origins = [o.strip() for o in self.allowed_origins_input.toPlainText().splitlines() if o.strip()]
        methods = [method for method, checkbox in self.method_checkboxes.items() if checkbox.isChecked()]
        
        if validate:
            if not origins:
                show_error_dialog("At least one origin is required")
                return None
                
            if not methods:
                show_error_dialog("At least one method must be selected")
                return None

        rule = {
            "AllowedOrigins": origins,
            "AllowedMethods": methods
        }

        headers = [h.strip() for h in self.allowed_headers_input.toPlainText().splitlines() if h.strip()]
        if headers:
            rule["AllowedHeaders"] = headers

        expose = [h.strip() for h in self.expose_headers_input.toPlainText().splitlines() if h.strip()]
        if expose:
            rule["ExposeHeaders"] = expose

        if self.max_age_input.text().strip():
            try:
                rule["MaxAgeSeconds"] = int(self.max_age_input.text())
            except ValueError:
                if validate:
                    show_error_dialog("Max Age must be a number")
                    return None

        return rule

    def _clear_form(self):
        """Clear all form fields"""
        self.allowed_origins_input.clear()
        for checkbox in self.method_checkboxes.values():
            checkbox.setChecked(False)
        self.allowed_headers_input.clear()
        self.expose_headers_input.clear()
        self.max_age_input.clear()
        self.save_rule_button.setEnabled(False)
        self.delete_rule_button.setEnabled(False)

    def delete_rule(self):
        """Delete selected CORS rule"""
        current_row = self.rules_list.currentRow()
        if current_row >= 0:
            self.rules_list.takeItem(current_row)
            self._clear_form()
            
            # Select last rule if any exist
            new_count = self.rules_list.count()
            if new_count > 0:
                last_row = new_count - 1
                self.rules_list.setCurrentRow(last_row)
                self.show_rule_details(last_row)  # Explicitly load the form
            else:
                self._enable_form(False)

    def apply_cors(self):
        """Apply CORS configuration to bucket"""
        try:
            rules = []
            
            # Update the current rule if one is selected
            current_item = self.rules_list.currentItem()
            if current_item:
                updated_rule = self._get_rule_from_form()
                if updated_rule:
                    current_item.setData(Qt.UserRole, updated_rule)
                    current_item.setText(f"{StringUtils.format_list_with_conjunction(updated_rule['AllowedMethods'])} on {', '.join(updated_rule['AllowedOrigins'])}")

            # Collect all rules
            for i in range(self.rules_list.count()):
                rules.append(self.rules_list.item(i).data(Qt.UserRole))

            if rules:
                s3_session.resource.meta.client.put_bucket_cors(
                    Bucket=self.bucket_name,
                    CORSConfiguration={
                        'CORSRules': rules
                    }
                )
            else:
                s3_session.resource.meta.client.delete_bucket_cors(Bucket=self.bucket_name)
            
            QMessageBox.information(self, "Success", "CORS configuration applied successfully")
            
        except Exception as e:
            show_error_dialog(e, show_traceback=True)

    def _enable_form(self, enabled=True):
        """Enable/disable all form fields"""
        self.allowed_origins_input.setEnabled(enabled)
        for checkbox in self.method_checkboxes.values():
            checkbox.setEnabled(enabled)
        self.allowed_headers_input.setEnabled(enabled)
        self.expose_headers_input.setEnabled(enabled)
        self.max_age_input.setEnabled(enabled)
        self.save_rule_button.setEnabled(False)  # Always start with save disabled
        self.delete_rule_button.setEnabled(enabled)