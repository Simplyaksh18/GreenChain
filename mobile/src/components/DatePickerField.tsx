/**
 * DatePickerField — GreenChain shared component (Phase 13)
 *
 * Renders a tappable date field that opens the native date picker.
 * On Android: inline dialog.
 * On iOS: bottom modal spinner.
 *
 * Props:
 *   label        — field label string
 *   value        — current date string in YYYY-MM-DD format (or "")
 *   onChange     — called with YYYY-MM-DD string on user selection
 *   maxDate      — optional max date (Date object) — use new Date() to block future dates
 *   minDate      — optional min date (Date object)
 *   accentColor  — outline/icon accent colour (default: #2e7d32)
 *   optional     — if true, shows "(optional)" in label; empty value is allowed
 *   disabled     — prevent opening the picker
 */
import React, { useState } from 'react';
import {
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  View,
} from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import DateTimePicker, {
  type DateTimePickerEvent,
} from '@react-native-community/datetimepicker';

// ── helpers ────────────────────────────────────────────────────────────────────

function toDate(iso: string): Date {
  if (!iso) return new Date();
  // Parse YYYY-MM-DD as local midnight (avoid timezone off-by-one)
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function toISO(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

// ── component ──────────────────────────────────────────────────────────────────

interface Props {
  label: string;
  value: string;                 // YYYY-MM-DD or ""
  onChange: (iso: string) => void;
  maxDate?: Date;
  minDate?: Date;
  accentColor?: string;
  optional?: boolean;
  disabled?: boolean;
}

export function DatePickerField({
  label,
  value,
  onChange,
  maxDate,
  minDate,
  accentColor = '#2e7d32',
  optional = false,
  disabled = false,
}: Props) {
  const [show, setShow] = useState(false);

  const displayLabel = optional ? `${label} (optional)` : label;
  const hasValue = !!value;

  // The date the picker should open at
  const pickerDate = hasValue ? toDate(value) : new Date();

  const handleChange = (_event: DateTimePickerEvent, selected?: Date) => {
    if (Platform.OS === 'android') {
      setShow(false);
    }
    if (selected) {
      onChange(toISO(selected));
    }
  };

  const handleClear = () => {
    if (optional) onChange('');
  };

  return (
    <View style={styles.wrapper}>
      <Pressable
        onPress={() => { if (!disabled) setShow(true); }}
        style={[
          styles.field,
          { borderColor: hasValue ? accentColor : '#9e9e9e' },
          disabled && styles.fieldDisabled,
        ]}
        accessibilityLabel={displayLabel}
        accessibilityRole="button"
      >
        {/* Floating label */}
        <Text
          style={[
            styles.floatingLabel,
            { color: hasValue ? accentColor : '#888', backgroundColor: 'rgba(255,255,255,0.9)' },
          ]}
        >
          {displayLabel}
        </Text>

        {/* Value or placeholder */}
        <View style={styles.row}>
          <MaterialCommunityIcons
            name="calendar"
            size={18}
            color={hasValue ? accentColor : '#aaa'}
            style={styles.icon}
          />
          <Text
            style={[
              styles.valueText,
              !hasValue && styles.placeholder,
            ]}
          >
            {hasValue ? value : 'Tap to select date'}
          </Text>

          {/* Clear button for optional fields */}
          {optional && hasValue && (
            <Pressable onPress={handleClear} hitSlop={8}>
              <MaterialCommunityIcons name="close-circle" size={16} color="#aaa" />
            </Pressable>
          )}
        </View>
      </Pressable>

      {/* Android: picker rendered inline when show=true */}
      {Platform.OS === 'android' && show && (
        <DateTimePicker
          value={pickerDate}
          mode="date"
          display="default"
          onChange={handleChange}
          maximumDate={maxDate}
          minimumDate={minDate}
        />
      )}

      {/* iOS: picker inside a bottom sheet modal */}
      {Platform.OS === 'ios' && (
        <Modal
          transparent
          visible={show}
          animationType="slide"
          onRequestClose={() => setShow(false)}
        >
          <Pressable style={styles.modalBackdrop} onPress={() => setShow(false)} />
          <View style={styles.iosSheet}>
            <View style={styles.iosSheetHeader}>
              <Pressable onPress={() => setShow(false)}>
                <Text style={styles.iosDone}>Done</Text>
              </Pressable>
            </View>
            <DateTimePicker
              value={pickerDate}
              mode="date"
              display="spinner"
              onChange={handleChange}
              maximumDate={maxDate}
              minimumDate={minDate}
              style={styles.iosPicker}
            />
          </View>
        </Modal>
      )}
    </View>
  );
}

// ── styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  wrapper: {
    marginBottom: 10,
  },
  field: {
    borderWidth: 1,
    borderRadius: 4,
    paddingHorizontal: 12,
    paddingTop: 18,
    paddingBottom: 10,
    backgroundColor: 'rgba(255,255,255,0.9)',
    minHeight: 56,
    justifyContent: 'center',
  },
  fieldDisabled: {
    opacity: 0.5,
  },
  floatingLabel: {
    position: 'absolute',
    top: -8,
    left: 8,
    fontSize: 12,
    fontWeight: '500',
    paddingHorizontal: 4,
    borderRadius: 2,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  icon: {
    marginRight: 8,
  },
  valueText: {
    flex: 1,
    fontSize: 16,
    color: '#333',
  },
  placeholder: {
    color: '#aaa',
  },
  // iOS modal
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.35)',
  },
  iosSheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingBottom: 24,
  },
  iosSheetHeader: {
    padding: 16,
    alignItems: 'flex-end',
    borderBottomWidth: 1,
    borderColor: '#eee',
  },
  iosDone: {
    color: '#2e7d32',
    fontSize: 16,
    fontWeight: '700',
  },
  iosPicker: {
    height: 200,
  },
});
