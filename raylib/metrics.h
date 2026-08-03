#pragma once

void metricsInit();
void metricsToggle();
bool metricsEnabled();
void metricsBeginFrame();
void metricsEndUpdate();
void metricsEndDraw();
void drawMetrics();
void metricsAddTextureBytes(int bytes);
