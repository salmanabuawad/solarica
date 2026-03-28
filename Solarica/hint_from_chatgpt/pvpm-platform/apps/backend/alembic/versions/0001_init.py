"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('devices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('serial_number', sa.String(), unique=True),
        sa.Column('model', sa.String()),
        sa.Column('firmware_version', sa.String()),
        sa.Column('calibration_date', sa.DateTime(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    )
    op.create_table('measurements',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('devices.id'), nullable=True),
        sa.Column('external_measurement_key', sa.String(), nullable=True),
        sa.Column('measured_at', sa.DateTime(), nullable=False),
        sa.Column('customer', sa.String(), nullable=True),
        sa.Column('installation', sa.String(), nullable=True),
        sa.Column('string_no', sa.String(), nullable=True),
        sa.Column('module_type', sa.String(), nullable=True),
        sa.Column('module_reference', sa.String(), nullable=True),
        sa.Column('modules_series', sa.Integer(), nullable=True),
        sa.Column('modules_parallel', sa.Integer(), nullable=True),
        sa.Column('nominal_power_w', sa.Float(), nullable=True),
        sa.Column('ppk_wp', sa.Float(), nullable=True),
        sa.Column('rs_ohm', sa.Float(), nullable=True),
        sa.Column('rp_ohm', sa.Float(), nullable=True),
        sa.Column('voc_v', sa.Float(), nullable=True),
        sa.Column('isc_a', sa.Float(), nullable=True),
        sa.Column('vpmax_v', sa.Float(), nullable=True),
        sa.Column('ipmax_a', sa.Float(), nullable=True),
        sa.Column('ff_percent', sa.Float(), nullable=True),
        sa.Column('sweep_duration_ms', sa.Float(), nullable=True),
        sa.Column('irradiance_w_m2', sa.Float(), nullable=True),
        sa.Column('sensor_temp_c', sa.Float(), nullable=True),
        sa.Column('module_temp_c', sa.Float(), nullable=True),
        sa.Column('irradiance_sensor_type', sa.String(), nullable=True),
        sa.Column('irradiance_sensor_serial', sa.String(), nullable=True),
        sa.Column('raw_payload_json', sa.JSON(), nullable=True),
        sa.Column('import_source', sa.String(), nullable=True),
        sa.Column('import_hash', sa.String(), nullable=True),
        sa.Column('sync_status', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )
    op.create_table('measurement_curve_points',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('measurement_id', sa.String(), sa.ForeignKey('measurements.id'), nullable=False),
        sa.Column('point_index', sa.Integer(), nullable=False),
        sa.Column('voltage_v', sa.Float(), nullable=False),
        sa.Column('current_a', sa.Float(), nullable=False),
    )
    op.create_table('sync_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('measurement_id', sa.String(), nullable=True),
        sa.Column('direction', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('sync_logs')
    op.drop_table('measurement_curve_points')
    op.drop_table('measurements')
    op.drop_table('devices')
