/**
 * RoleBackground — wraps any screen in the correct background image
 * for the current user's role.
 *
 * Reads role from authStore automatically. Pass role="AUTH" explicitly
 * for login/register screens (unauthenticated context).
 *
 * Props:
 *   role?      — override role ('FARMER'|'FPO'|'VERIFIER'|'ADMIN'|'AUTH')
 *   children   — screen content
 *   overlay?   — custom overlay colour; defaults to role-specific dark tint
 */
import React from 'react';
import {
  ImageBackground,
  View,
  StyleSheet,
  ViewStyle,
  ImageSourcePropType,
} from 'react-native';

import { useAuthStore } from '../store/authStore';

type RoleName = 'FARMER' | 'FPO' | 'VERIFIER' | 'ADMIN' | 'AUTH';

const BACKGROUNDS: Record<RoleName, ImageSourcePropType> = {
  FARMER:   require('../../assets/images/bg_farmer.jpg'),
  FPO:      require('../../assets/images/bg_farmer.jpg'), // FPO reuses farmer background
  VERIFIER: require('../../assets/images/bg_verifier.jpg'),
  ADMIN:    require('../../assets/images/bg_admin.jpg'),
  AUTH:     require('../../assets/images/bg_login.jpg'),
};

const OVERLAYS: Record<RoleName, string> = {
  FARMER:   'rgba(5,35,10,0.58)',
  FPO:      'rgba(5,25,50,0.55)',
  VERIFIER: 'rgba(5,50,20,0.55)',
  ADMIN:    'rgba(10,10,20,0.62)',
  AUTH:     'rgba(10,40,15,0.68)',
};

interface Props {
  /** Override role; if omitted the component reads from authStore */
  role?: RoleName | string;
  children: React.ReactNode;
  /** Extra style applied to the inner safe container */
  contentStyle?: ViewStyle;
}

export function RoleBackground({ role, children, contentStyle }: Props) {
  const storeRole = useAuthStore((s) => s.user?.role);
  const resolved = (role ?? storeRole ?? 'AUTH') as RoleName;
  const source = BACKGROUNDS[resolved] ?? BACKGROUNDS.AUTH;
  const overlayColor = OVERLAYS[resolved] ?? OVERLAYS.AUTH;

  return (
    <ImageBackground source={source} style={styles.bg} resizeMode="cover">
      <View style={[styles.overlay, { backgroundColor: overlayColor }]} />
      <View style={[styles.content, contentStyle]}>{children}</View>
    </ImageBackground>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
  overlay: { ...StyleSheet.absoluteFillObject },
  content: { flex: 1 },
});
