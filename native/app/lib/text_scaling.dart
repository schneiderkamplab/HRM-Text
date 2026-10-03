import 'package:flutter/painting.dart';

/// Apply the app preference after the system's (possibly nonlinear) scaling.
class AppTextScaler extends TextScaler {
  final TextScaler system;
  final double factor;

  const AppTextScaler(this.system, this.factor);

  @override
  double scale(double fontSize) => system.scale(fontSize) * factor;

  @override
  // Required legacy estimate; layout uses scale() and retains nonlinearity.
  double get textScaleFactor => scale(14) / 14;

  @override
  bool operator ==(Object other) =>
      other is AppTextScaler &&
      other.system == system &&
      other.factor == factor;

  @override
  int get hashCode => Object.hash(system, factor);
}
