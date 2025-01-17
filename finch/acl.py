from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QGroupBox, QTableWidget, \
    QTableWidgetItem, QComboBox, QPushButton, QHeaderView, QHBoxLayout, QLabel, QFrame, QMessageBox

from finch.common import center_window, s3_session
from finch.error import show_error_dialog

ALL_USER_GROUP_URI = 'http://acs.amazonaws.com/groups/global/AllUsers'
AUTHENTICATED_USER_GROUP_URI = 'http://acs.amazonaws.com/groups/global/AuthenticatedUsers'
S3_LOG_DELIVERY_URI = 'http://acs.amazonaws.com/groups/global/LogDelivery'


class ACLWindow(QWidget):
    """
    ACL Window to manage ACL configurations for passed bucket name.
    """

    def __init__(self, bucket_name):
        super().__init__()
        self.bucket_name = bucket_name
        self.setWindowTitle(f"ACL Configurations - {bucket_name}")
        self.resize(800, 600)
        center_window(self)

        layout = QVBoxLayout()
        rule_group = QGroupBox("ACL Rules")
        rule_layout = QVBoxLayout()
        rule_group.setLayout(rule_layout)
        bucket_owner_title_label = QLabel("Bucket Owner:")
        bold_font = QFont()
        bold_font.setBold(True)
        bucket_owner_title_label.setFont(bold_font)
        rule_layout.addWidget(bucket_owner_title_label)
        self.bucket_owner_input = QLineEdit()
        rule_layout.addWidget(self.bucket_owner_input)
        bucket_owner_displayname_title_label = QLabel("Bucket Owner Display Name:")
        bucket_owner_displayname_title_label.setFont(bold_font)
        rule_layout.addWidget(bucket_owner_displayname_title_label)
        self.bucket_owner_displayname_label = QLabel("")
        self.bucket_owner_displayname_label.setFrameStyle(QFrame.Box | QFrame.Raised)
        rule_layout.addWidget(self.bucket_owner_displayname_label)
        permissions_title_label = QLabel("Permissions:")
        permissions_title_label.setFont(bold_font)
        rule_layout.addWidget(permissions_title_label)
        fine_grained_permission_widget = QWidget()
        fine_grained_permission_layout = QVBoxLayout()
        self.fine_grained_permission_table = QTableWidget()
        self.fine_grained_permission_table.setColumnCount(3)
        self.fine_grained_permission_table.setHorizontalHeaderLabels(["Grantee Type", "Grantee ID/URI", "Permission"])
        header = self.fine_grained_permission_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.add_fine_grained_permission_button = QPushButton("Add Permission")
        self.add_fine_grained_permission_button.clicked.connect(self.add_fine_grained_permission)
        self.delete_fine_grained_permission_button = QPushButton("Delete Permission")
        self.delete_fine_grained_permission_button.clicked.connect(self.delete_fine_grained_permission)
        self.delete_fine_grained_permission_button.setEnabled(False)  # Initially disabled

        # Add selection change handler
        self.fine_grained_permission_table.itemSelectionChanged.connect(self.on_permission_selection_changed)

        fine_grained_permission_buttons = QWidget()
        fine_grained_permission_layout.addWidget(self.fine_grained_permission_table)
        fine_grained_permission_buttons_layout = QHBoxLayout()
        fine_grained_permission_buttons_layout.addWidget(self.add_fine_grained_permission_button)
        fine_grained_permission_buttons_layout.addWidget(self.delete_fine_grained_permission_button)
        fine_grained_permission_buttons.setLayout(fine_grained_permission_buttons_layout)
        fine_grained_permission_layout.addWidget(fine_grained_permission_buttons)
        fine_grained_permission_widget.setLayout(fine_grained_permission_layout)
        rule_layout.addWidget(fine_grained_permission_widget)
        layout.addWidget(rule_group)
        save_config_button = QPushButton("Save ACL Configuration")
        save_config_button.clicked.connect(self.save_acl_rules)
        layout.addWidget(save_config_button)
        self.setLayout(layout)
        self.load_acl_rules()

    def add_fine_grained_permission(self, grantee_type: str = None, grantee_id_uri: str = None,
                                    permission: str = None) -> None:
        """
        Add a new permission row to the ACL table.
        
        Args:
            grantee_type: Type of grantee (Canonical User or Group)
            grantee_id_uri: ID or URI of the grantee
            permission: Permission to grant
        """
        current_row_position = self.fine_grained_permission_table.rowCount()
        self.fine_grained_permission_table.insertRow(current_row_position)
        self.fine_grained_permission_table.setItem(current_row_position, 0, QTableWidgetItem(""))
        grantee_type_combobox = QComboBox()
        grantee_type_combobox.addItems(["Canonical User", "Group"])

        if grantee_type:
            grantee_type_combobox.setCurrentText(grantee_type)
        permission_combobox = QComboBox()
        permission_combobox.addItems(["READ", "WRITE", "READ_ACP", "WRITE_ACP", "FULL_CONTROL"])
        if permission:
            permission_combobox.setCurrentText(permission)

        self.fine_grained_permission_table.setCellWidget(current_row_position, 0, grantee_type_combobox)
        group_id_uri_combobox = QComboBox()
        group_id_uri_combobox.addItems([ALL_USER_GROUP_URI, AUTHENTICATED_USER_GROUP_URI, S3_LOG_DELIVERY_URI])
        group_id_uri_combobox.setEditable(True)
        self.fine_grained_permission_table.setCellWidget(current_row_position, 1, group_id_uri_combobox)
        self.fine_grained_permission_table.setCellWidget(current_row_position, 2, permission_combobox)

        if grantee_id_uri:
            group_id_uri_combobox.setCurrentText(grantee_id_uri)
        else:
            group_id_uri_combobox.setCurrentText("")

    def on_permission_selection_changed(self) -> None:
        """Enable/disable delete button based on row selection."""
        self.delete_fine_grained_permission_button.setEnabled(
            len(self.fine_grained_permission_table.selectedItems()) > 0
        )

    def delete_fine_grained_permission(self):
        selected_row = self.fine_grained_permission_table.currentRow()
        if selected_row >= 0:
            self.fine_grained_permission_table.removeRow(selected_row)

    def load_acl_rules(self):
        acl = s3_session.resource.meta.client.get_bucket_acl(Bucket=self.bucket_name)
        self.bucket_owner_input.setText(acl['Owner']['ID'])
        self.bucket_owner_displayname_label.setText(acl['Owner']['DisplayName'])
        if 'Grants' in acl:
            for grant in acl['Grants']:
                if grant['Grantee']['Type'] == 'CanonicalUser':
                    self.add_fine_grained_permission(grant['Grantee']['Type'], grant['Grantee']['ID'],
                                                     grant['Permission'])
                else:
                    self.add_fine_grained_permission(grant['Grantee']['Type'], grant['Grantee']['URI'],
                                                     grant['Permission'])

    def validate_acl_rules(self) -> bool:
        """
        Validate ACL rules before saving.
        
        Returns:
            bool: True if validation passes, False otherwise
        """
        if not self.bucket_owner_input.text().strip():
            show_error_dialog("Validation Error: Bucket owner ID cannot be empty")
            return False

        for row in range(self.fine_grained_permission_table.rowCount()):
            grantee_id_uri = self.fine_grained_permission_table.cellWidget(row, 1).currentText()
            if not grantee_id_uri.strip():
                show_error_dialog(f"Validation Error: Grantee ID/URI cannot be empty at row {row + 1}")
                return False

        return True

    def save_acl_rules(self) -> None:
        """Save ACL rules to the S3 bucket."""
        if not self.validate_acl_rules():
            return

        owner = {
            'ID': self.bucket_owner_input.text().strip(),
        }

        grants = []
        for row in range(self.fine_grained_permission_table.rowCount()):
            grantee_type = self.fine_grained_permission_table.cellWidget(row, 0).currentText()
            grantee_id_uri = self.fine_grained_permission_table.cellWidget(row, 1).currentText().strip()
            permission = self.fine_grained_permission_table.cellWidget(row, 2).currentText()

            grantee = {
                'Type': 'CanonicalUser' if grantee_type == 'Canonical User' else 'Group'
            }

            if grantee['Type'] == 'CanonicalUser':
                grantee['ID'] = grantee_id_uri
            else:  # Group
                grantee['URI'] = grantee_id_uri

            grants.append({
                'Grantee': grantee,
                'Permission': permission
            })

        acl = {
            'Owner': owner,
            'Grants': grants
        }

        try:
            s3_session.resource.meta.client.put_bucket_acl(
                Bucket=self.bucket_name,
                AccessControlPolicy=acl
            )
            QMessageBox.information(self, "Success", "ACL configuration saved successfully")
        except Exception as e:
            show_error_dialog(e, show_traceback=True, extra_info=f"ACL Rule JSON: {acl}")

