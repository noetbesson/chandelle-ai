// The drawing stays vector-native: each flame has its own anchored group.
export function candleDrawing(){
  const flame=(x,y,delay)=>`<g transform="translate(${x} ${y})"><g class="candle-flame" style="--flicker-delay:${delay}s"><path class="flame-outer" d="M0 0 C-20 -4 -20 -23 -11 -42 C-5 -55 -2 -66 -3 -75 C8 -59 11 -45 16 -31 C24 -13 13 -2 0 0Z"/><path class="flame-inner" d="M0 -8 C-7 -14 -7 -23 -2 -33 C1 -39 2 -44 2 -48 C7 -34 11 -24 9 -18 C7 -12 4 -9 0 -8Z"/></g></g>`;
  return `<svg class="voice-candles" viewBox="0 -65 300 440" aria-hidden="true" focusable="false">
    <g class="candle-ink" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M72 128 L70 116 M150 91 L150 79 M228 128 L228 116"/>
      <path d="M61 131 Q72 127 82 131 L84 250 Q72 254 61 250Z M139 95 Q150 91 161 95 L160 239 Q149 241 138 239Z M217 131 Q228 127 240 132 L239 251 Q228 254 217 251Z"/>
      <path d="M63 134 Q71 141 67 174 M141 99 Q148 107 144 158 M220 135 Q228 143 223 185" stroke-width="3"/>
      <path d="M52 253 Q72 248 92 253 L90 263 Q72 268 53 262Z M130 240 Q150 236 171 241 L168 251 Q150 254 130 250Z M207 254 Q228 249 249 254 L247 265 Q228 269 208 263Z"/>
      <path d="M60 267 Q58 288 76 288 Q88 286 84 267 M138 254 Q135 277 152 277 Q165 275 162 254 M216 269 Q213 290 230 290 Q243 286 240 269"/>
      <path d="M74 289 Q73 316 107 301 Q132 286 146 300 M230 290 Q225 315 194 301 Q171 286 155 300 M146 280 L145 309 Q136 319 151 322 Q165 319 156 309 L155 280"/>
      <path d="M143 319 Q112 308 88 334 Q77 354 109 340Z M159 320 Q187 308 211 334 Q225 354 191 340Z M142 323 Q127 344 119 360 L132 354 L133 365 Q147 342 149 328 M157 324 Q169 348 185 360 L176 346 L190 351 Q175 332 164 326" stroke-width="3.5"/>
      <path d="M150 328 L150 347 Q147 355 140 357 L129 363 Q125 367 138 368 L165 368 Q177 366 169 362 L158 357 Q152 353 153 346"/>
    </g>${flame(72,116,-.5)}${flame(150,79,-1.3)}${flame(228,116,-.9)}</svg>`;
}
