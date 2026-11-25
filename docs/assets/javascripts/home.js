/* ---------------------------------------------------------------------------
   Home page animation — a sandbox of Docker Sandboxes, drawn on the canvas of
   the hero of `overrides/home.html`.

   A glass cube, the sandbox, stands on a glowing slab over a dark grid that
   fades into the distance; construction lines rise from its corners. Its
   contents are throw-away: three cubes drop into it one by one, a plane of
   light rises through it while it runs, then they lift out
   and fade, and an empty cube waits for the next run. Pulses run along the
   grid towards the slab, the requests of the socket, and the edges of the
   cube brighten when one arrives; far away, small ghost cubes appear and
   dissolve, the other sandboxes of the daemon.

   Everything is drawn with the 2D canvas API and a hand-written projection,
   so the page needs no library and no build step: the world turns around the
   vertical axis, leans towards the viewer, then goes through a perspective.
   Faces are drawn back to front, the back of the glass first, then the slab
   and the cubes it holds (lower layer first, then by depth), then the front
   of the glass. With `prefers-reduced-motion` one still frame is drawn, the
   cubes in place. `overrides/main.html` loads this file on every page,
   since the theme's instant navigation does not run the scripts of the page
   it arrives on; it does nothing on a page without the hero. It also makes
   the install command of the hero copy itself on a click.
   --------------------------------------------------------------------------- */

(function () {
    "use strict";

    /* Colors, as channels: the white of the glass and the indigo of the
       pulses, the one accent of the site's palette. */
    var WHITE = [236, 240, 255];
    var INDIGO = [128, 142, 255];

    /* World units, y up. The cube spans [-1, 1] on x and z and [0, 2] on y;
       the slab under it is wider and `SLAB_DEPTH` thick, its top at y = 0.
       The grid lies on the floor under the slab, `GRID_STEP` apart, and fades
       out at `GRID_FADE` from the center. */
    var CUBE = 1;
    var HEIGHT = 2;
    var SLAB = 1.24;
    var SLAB_DEPTH = 0.1;
    var FLOOR = -SLAB_DEPTH;
    var GRID_STEP = 0.5;
    var GRID_HALF = 7.5;
    var GRID_FADE = 7;

    /* The camera: its distance, the turn that shows a corner of the cube to
       the viewer, the lean towards it, and how far both sway. */
    var CAMERA = 12;
    var YAW = Math.PI / 4;
    var YAW_SWAY = 0.2;
    var PITCH = 0.58;
    var PITCH_SWAY = 0.03;

    /* The cubes the sandbox holds: half the side of one, then each one's
       place on the floor of the sandbox, its layer and its drop and lift
       times in the cycle, in seconds. The top one rests on the two below. */
    var HALF = 0.29;
    var SIDE = 2 * HALF;
    var BLOCKS = [
        { x: -0.32, z: 0.18, layer: 0, drop: 0.5, lift: 9.9 },
        { x: 0.3, z: -0.16, layer: 0, drop: 1.25, lift: 9.5 },
        { x: 0, z: 0, layer: 1, drop: 2.0, lift: 9.1 },
    ];
    var DROP = 1.1;
    var LIFT = 1.2;
    var FALL = 2.4;

    /* The cycle: its length, the two sweeps of the plane of light, and the
       wipe of the edges that marks a fresh sandbox. */
    var CYCLE = 13;
    var SWEEPS = [
        [3.5, 5.9],
        [6.1, 8.5],
    ];
    var WIPE = [11.3, 12.5];

    /* Pulses: seconds between two, at rest and while the sandbox runs, and
       the most in flight. */
    var PULSE_IDLE = [0.45, 1.0];
    var PULSE_BUSY = [0.16, 0.38];
    var PULSE_CAP = 24;

    var GHOSTS = 4;

    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var wide = window.matchMedia("(min-width: 76.25em)");

    /* The glow sprite, built once: a radial falloff that every dot, pulse
       and halo is a scaled copy of. */
    function makeSprite(rgb) {
        var sprite = document.createElement("canvas");
        sprite.width = 64;
        sprite.height = 64;
        var sctx = sprite.getContext("2d");
        var gradient = sctx.createRadialGradient(32, 32, 0, 32, 32, 32);
        var c = rgb.join(",");
        gradient.addColorStop(0, "rgba(255,255,255,1)");
        gradient.addColorStop(0.14, "rgba(" + c + ",0.9)");
        gradient.addColorStop(0.35, "rgba(" + c + ",0.35)");
        gradient.addColorStop(0.65, "rgba(" + c + ",0.08)");
        gradient.addColorStop(1, "rgba(" + c + ",0)");
        sctx.fillStyle = gradient;
        sctx.fillRect(0, 0, 64, 64);
        return sprite;
    }

    var GLOW_WHITE = makeSprite(WHITE);
    var GLOW_INDIGO = makeSprite(INDIGO);

    /* Easing and small helpers. */
    function clamp(v, lo, hi) {
        return v < lo ? lo : v > hi ? hi : v;
    }

    function smooth(a, b, t) {
        var x = clamp((t - a) / (b - a), 0, 1);
        return x * x * (3 - 2 * x);
    }

    function lerp(a, b, f) {
        return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
    }

    function rgba(rgb, alpha) {
        return "rgba(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + "," + alpha.toFixed(3) + ")";
    }

    /* The eight corners of a box and its six faces, each listed
       counter-clockwise as seen from outside, with its outward normal. A face
       whose projection turns the same way faces the camera. */
    function corners(x0, y0, z0, x1, y1, z1) {
        return [
            [x0, y0, z0],
            [x1, y0, z0],
            [x1, y1, z0],
            [x0, y1, z0],
            [x0, y0, z1],
            [x1, y0, z1],
            [x1, y1, z1],
            [x0, y1, z1],
        ];
    }

    var FACES = [
        { idx: [0, 3, 2, 1], normal: [0, 0, -1] },
        { idx: [4, 5, 6, 7], normal: [0, 0, 1] },
        { idx: [0, 4, 7, 3], normal: [-1, 0, 0] },
        { idx: [1, 2, 6, 5], normal: [1, 0, 0] },
        { idx: [0, 1, 5, 4], normal: [0, -1, 0] },
        { idx: [3, 7, 6, 2], normal: [0, 1, 0] },
    ];

    var EDGES = [
        [0, 1], [1, 2], [2, 3], [3, 0],
        [4, 5], [5, 6], [6, 7], [7, 4],
        [0, 4], [1, 5], [2, 6], [3, 7],
    ];

    /* The faces each edge borders, for telling front edges from back ones. */
    var EDGE_FACES = EDGES.map(function (edge) {
        var faces = [];
        FACES.forEach(function (face, f) {
            if (face.idx.indexOf(edge[0]) >= 0 && face.idx.indexOf(edge[1]) >= 0) {
                faces.push(f);
            }
        });
        return faces;
    });

    var CUBE_CORNERS = corners(-CUBE, 0, -CUBE, CUBE, HEIGHT, CUBE);
    var SLAB_CORNERS = corners(-SLAB, FLOOR, -SLAB, SLAB, 0, SLAB);

    /* The light of the cubes: from above, on the left of the viewer. */
    var LIGHT = (function () {
        var v = [-0.45, 0.8, 0.4];
        var n = Math.hypot(v[0], v[1], v[2]);
        return [v[0] / n, v[1] / n, v[2] / n];
    })();

    /* Live state: the canvas and its context, its size, the camera of the
       frame, the pulses, pings and ghosts, the flash of the edges, and the
       generation of the frame loop. The theme's instant navigation swaps the
       page without reloading it, so the hero is looked up again on every
       arrival and the loop of a hero that left the page stops by its
       generation. */
    var hero = null;
    var canvas = null;
    var ctx = null;
    var observer = null;
    var visibility = null;
    var visible = true;
    var size = { width: 0, height: 0, dpr: 1, room: 0 };
    var view = { cosY: 1, sinY: 0, cosP: 1, sinP: 0, cx: 0, cy: 0, unit: 1, pivot: 0.95 };
    var pulses = [];
    var pings = [];
    var ghosts = [];
    var flash = 0;
    var landing = 0;
    var nextPulse = 0.3;
    var generation = 0;
    var last = 0;
    var elapsed = 0;

    /* Projects a world point into `out`: x and y in pixels, the scale of the
       perspective there and the depth towards the camera. */
    function project(p, out) {
        var x = p[0] * view.cosY - p[2] * view.sinY;
        var z = p[0] * view.sinY + p[2] * view.cosY;
        var y0 = p[1] - view.pivot;
        var y = y0 * view.cosP - z * view.sinP;
        z = y0 * view.sinP + z * view.cosP;
        var scale = CAMERA / (CAMERA - Math.min(z, CAMERA - 1));
        out = out || [0, 0, 0, 0];
        out[0] = view.cx + x * view.unit * scale;
        out[1] = view.cy - y * view.unit * scale;
        out[2] = scale;
        out[3] = z;
        return out;
    }

    /* Twice the signed area of a projected polygon: negative when it turns
       counter-clockwise on the screen, that is when its face is seen. */
    function area(points) {
        var sum = 0;
        for (var i = 0; i < points.length; i++) {
            var a = points[i];
            var b = points[(i + 1) % points.length];
            sum += a[0] * b[1] - b[0] * a[1];
        }
        return sum;
    }

    function path(points) {
        ctx.beginPath();
        ctx.moveTo(points[0][0], points[0][1]);
        for (var i = 1; i < points.length; i++) {
            ctx.lineTo(points[i][0], points[i][1]);
        }
        ctx.closePath();
    }

    /* A glowing line: a wide faint stroke, a narrower one and the core. */
    function glowLine(a, b, width, alpha, rgb) {
        rgb = rgb || WHITE;
        var passes = [
            [width * 7, alpha * 0.05],
            [width * 3, alpha * 0.14],
            [width, alpha],
        ];
        passes.forEach(function (pass) {
            ctx.lineWidth = pass[0];
            ctx.strokeStyle = rgba(rgb, pass[1]);
            ctx.beginPath();
            ctx.moveTo(a[0], a[1]);
            ctx.lineTo(b[0], b[1]);
            ctx.stroke();
        });
    }

    function glow(sprite, x, y, radius, alpha) {
        if (alpha <= 0.002) {
            return;
        }
        ctx.globalAlpha = Math.min(1, alpha);
        ctx.drawImage(sprite, x - radius, y - radius, radius * 2, radius * 2);
        ctx.globalAlpha = 1;
    }

    /* How faint the floor is at distance `r` from the center. */
    function fade(r) {
        var f = 1 - r / GRID_FADE;
        return f <= 0 ? 0 : Math.pow(f, 1.7);
    }

    /* Places the camera for this frame and the cube on the screen: on the
       right of the hero on wide screens, in its upper part on narrow ones. */
    function frame(now) {
        var yaw = YAW + (reduced ? 0.08 : YAW_SWAY * Math.sin(now * 0.09));
        var pitch = PITCH + (reduced ? 0 : PITCH_SWAY * Math.sin(now * 0.13));
        view.cosY = Math.cos(yaw);
        view.sinY = Math.sin(yaw);
        view.cosP = Math.cos(pitch);
        view.sinP = Math.sin(pitch);
        if (wide.matches) {
            view.cx = size.width * 0.7;
            view.cy = size.height * 0.53;
            view.unit = Math.min(size.height * 0.15, size.width * 0.1);
        } else {
            /* Above the text: `room` is the height left over it, which the
               cube, its slab and its construction lines fill. */
            view.unit = Math.min(size.room / 4.6, size.width * 0.17);
            view.cx = size.width * 0.5;
            view.cy = size.room * 0.08 + view.unit * 2.4;
        }
    }

    /* The grid of the floor. Segments are grouped by brightness, so a frame
       strokes a dozen paths rather than a thousand lines; the lines that run
       along the faces of the cube are brighter, as construction lines. */
    function drawGrid() {
        var BUCKETS = 12;
        var buckets = [];
        var strong = [];
        for (var b = 0; b < BUCKETS; b++) {
            buckets.push([]);
        }
        var a = [0, 0, 0, 0];
        var c = [0, 0, 0, 0];
        var limit = CAMERA - 2.5;
        for (var k = -GRID_HALF; k <= GRID_HALF + 1e-6; k += GRID_STEP) {
            var guide = Math.abs(Math.abs(k) - CUBE) < 1e-6;
            for (var s = -GRID_HALF; s < GRID_HALF - 1e-6; s += GRID_STEP) {
                for (var dir = 0; dir < 2; dir++) {
                    var p0 = dir ? [s, FLOOR, k] : [k, FLOOR, s];
                    var p1 = dir ? [s + GRID_STEP, FLOOR, k] : [k, FLOOR, s + GRID_STEP];
                    var mx = (p0[0] + p1[0]) / 2;
                    var mz = (p0[2] + p1[2]) / 2;
                    var f = fade(Math.hypot(mx, mz));
                    if (f <= 0.01) {
                        continue;
                    }
                    project(p0, a);
                    project(p1, c);
                    if (a[3] > limit || c[3] > limit) {
                        continue;
                    }
                    var seg = [a[0], a[1], c[0], c[1]];
                    if (guide) {
                        strong.push([seg, f]);
                    } else {
                        buckets[Math.min(BUCKETS - 1, Math.floor(f * BUCKETS))].push(seg);
                    }
                }
            }
        }
        ctx.lineWidth = 1;
        buckets.forEach(function (segments, i) {
            if (!segments.length) {
                return;
            }
            ctx.strokeStyle = rgba(WHITE, 0.16 * ((i + 0.5) / BUCKETS));
            ctx.beginPath();
            segments.forEach(function (seg) {
                ctx.moveTo(seg[0], seg[1]);
                ctx.lineTo(seg[2], seg[3]);
            });
            ctx.stroke();
        });
        strong.forEach(function (item) {
            var seg = item[0];
            glowLine([seg[0], seg[1]], [seg[2], seg[3]], 1, 0.42 * item[1]);
        });
    }

    /* A few crossings of the grid near the cube glint, each at its own pace. */
    var GLINTS = [];
    (function () {
        for (var i = 0; i < 26; i++) {
            var gx = Math.round((Math.random() * 2 - 1) * 9) * GRID_STEP;
            var gz = Math.round((Math.random() * 2 - 1) * 9) * GRID_STEP;
            if (Math.abs(gx) <= SLAB && Math.abs(gz) <= SLAB) {
                continue;
            }
            GLINTS.push({ p: [gx, FLOOR, gz], phase: Math.random() * Math.PI * 2, speed: 0.4 + Math.random() * 0.8 });
        }
    })();

    function drawGlints(now) {
        var s = [0, 0, 0, 0];
        GLINTS.forEach(function (glint) {
            var f = fade(Math.hypot(glint.p[0], glint.p[2]));
            var blink = reduced ? 0.6 : 0.5 + 0.5 * Math.sin(now * glint.speed + glint.phase);
            project(glint.p, s);
            glow(GLOW_WHITE, s[0], s[1], 6 * s[2], 0.55 * f * blink * blink);
        });
    }

    /* The glow of the slab on the floor around it. */
    function drawHalo() {
        var s = project([0, FLOOR, 0]);
        var radius = 2.9 * view.unit * s[2];
        ctx.save();
        ctx.translate(s[0], s[1]);
        ctx.scale(1, view.sinP * 0.95);
        var gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
        gradient.addColorStop(0, rgba(WHITE, 0.26 + 0.12 * landing));
        gradient.addColorStop(0.4, rgba(WHITE, 0.08 + 0.04 * landing));
        gradient.addColorStop(1, rgba(WHITE, 0));
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(0, 0, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    /* Ghost cubes: small sandboxes far on the grid, whose edges draw
       themselves in, hold, and dissolve. */
    function spawnGhost(ghost, now) {
        for (var tries = 0; tries < 20; tries++) {
            var gx = Math.round((Math.random() * 2 - 1) * 11) * GRID_STEP;
            var gz = Math.round((Math.random() * 2 - 1) * 11) * GRID_STEP;
            var r = Math.hypot(gx, gz);
            /* Far from the cube, on the far side of the floor where the grid
               is still visible, and off to a side, so that none shows
               through the glass; on wide screens on its right, away from the
               text. */
            var side = gx - gz;
            if (r < 2.6 || r > 5.4 || gx + gz > 0.5 || Math.abs(side) < 3.4 || (wide.matches && side < 0)) {
                continue;
            }
            var clash = ghosts.some(function (other) {
                return other !== ghost && other.until > now && Math.hypot(other.x - gx, other.z - gz) < 1.2;
            });
            if (clash) {
                continue;
            }
            ghost.x = gx;
            ghost.z = gz;
            ghost.half = 0.14 + Math.random() * 0.14;
            ghost.start = now + Math.random() * 2.5;
            ghost.hold = 2.5 + Math.random() * 3;
            ghost.until = ghost.start + 0.9 + ghost.hold + 1.1;
            return;
        }
        ghost.start = now + 1;
        ghost.until = now + 1;
    }

    function drawGhosts(now) {
        var pts = [];
        ghosts.forEach(function (ghost) {
            if (now >= ghost.until) {
                spawnGhost(ghost, now);
            }
            var t = now - ghost.start;
            if (t < 0) {
                return;
            }
            var grow = smooth(0, 0.9, t);
            var alpha = 1 - smooth(0.9 + ghost.hold, ghost.until - ghost.start, t);
            if (reduced) {
                grow = 1;
                alpha = 1;
            }
            var h = ghost.half;
            var box = corners(ghost.x - h, FLOOR, ghost.z - h, ghost.x + h, FLOOR + 2 * h, ghost.z + h);
            for (var i = 0; i < 8; i++) {
                pts[i] = project(box[i], pts[i]);
            }
            var f = fade(Math.hypot(ghost.x, ghost.z)) * alpha;
            ctx.lineWidth = 1;
            ctx.strokeStyle = rgba(WHITE, 0.5 * f);
            ctx.beginPath();
            EDGES.forEach(function (edge) {
                var a = pts[edge[0]];
                var b = pts[edge[1]];
                ctx.moveTo(a[0], a[1]);
                ctx.lineTo(a[0] + (b[0] - a[0]) * grow, a[1] + (b[1] - a[1]) * grow);
            });
            ctx.stroke();
            var top = project([ghost.x, FLOOR + 2 * h, ghost.z]);
            glow(GLOW_WHITE, top[0], top[1], 10 * top[2], 0.25 * f * grow);
        });
    }

    /* Pulses: a light running along a grid line from the distance to the
       slab, with a fading trail. Its arrival lights the edges of the cube and
       leaves a ring on the floor. */
    function spawnPulse(now) {
        var lanes = [-1, -0.5, 0, 0.5, 1];
        var axis = Math.random() < 0.5 ? "x" : "z";
        var sign = Math.random() < 0.5 ? -1 : 1;
        pulses.push({
            axis: axis,
            lane: lanes[Math.floor(Math.random() * lanes.length)],
            sign: sign,
            start: now,
            duration: 2.1 + Math.random() * 1.1,
            from: 6.6,
        });
    }

    function pulsePoint(pulse, d) {
        return pulse.axis === "x" ? [pulse.sign * d, FLOOR, pulse.lane] : [pulse.lane, FLOOR, pulse.sign * d];
    }

    function drawPulses(now) {
        var s = [0, 0, 0, 0];
        pulses.forEach(function (pulse) {
            var t = clamp((now - pulse.start) / pulse.duration, 0, 1);
            var eased = t * t * (3 - 2 * t);
            var d = pulse.from + (SLAB - pulse.from) * eased;
            for (var k = 0; k < 9; k++) {
                var dk = Math.min(pulse.from, d + k * 0.11);
                var p = pulsePoint(pulse, dk);
                var f = fade(Math.hypot(p[0], p[2])) * 0.85 + 0.15;
                project(p, s);
                glow(GLOW_INDIGO, s[0], s[1], (9 - k * 0.8) * s[2], (1 - k * 0.1) * f * smooth(0, 0.08, t));
            }
        });
        pings.forEach(function (ping) {
            var t = (now - ping.start) / 0.9;
            var s0 = project(ping.p);
            ctx.save();
            ctx.translate(s0[0], s0[1]);
            ctx.scale(1, view.sinP);
            ctx.lineWidth = 1.2;
            ctx.strokeStyle = rgba(INDIGO, 0.6 * (1 - t));
            ctx.beginPath();
            ctx.arc(0, 0, (0.05 + 0.35 * t) * view.unit * s0[2], 0, Math.PI * 2);
            ctx.stroke();
            ctx.restore();
        });
    }

    /* The slab: dark faces, a fine inner frame on its top and glowing edges. */
    function drawSlab(bright) {
        var pts = SLAB_CORNERS.map(function (p) {
            return project(p);
        });
        var seen = [];
        FACES.forEach(function (face, f) {
            var poly = face.idx.map(function (i) {
                return pts[i];
            });
            if (area(poly) < 0) {
                seen[f] = true;
                path(poly);
                ctx.fillStyle = face.normal[1] > 0 ? "#111319" : "#0b0c10";
                ctx.fill();
            }
        });
        ctx.globalCompositeOperation = "lighter";
        var inset = corners(-SLAB + 0.1, 0, -SLAB + 0.1, SLAB - 0.1, 0, SLAB - 0.1);
        var inner = [inset[0], inset[1], inset[5], inset[4]].map(function (p) {
            return project(p);
        });
        path(inner);
        ctx.lineWidth = 1;
        ctx.strokeStyle = rgba(WHITE, 0.1 + 0.08 * landing);
        ctx.stroke();
        EDGES.forEach(function (edge, e) {
            var front = EDGE_FACES[e].some(function (f) {
                return seen[f];
            });
            if (front) {
                glowLine(pts[edge[0]], pts[edge[1]], 1, (0.4 + 0.35 * landing) * bright);
            }
        });
        ctx.globalCompositeOperation = "source-over";
    }

    /* Where a cube is at `t` of the cycle: how far above its place, and how
       opaque; `null` while it is out of the sandbox. */
    function blockState(box, t) {
        if (reduced) {
            return { lift: 0, alpha: 1 };
        }
        if (t < box.drop || t > box.lift + LIFT) {
            return null;
        }
        if (t < box.drop + DROP) {
            var p = (t - box.drop) / DROP;
            var e = 1 - Math.pow(1 - p, 3);
            return { lift: (1 - e) * FALL, alpha: clamp(p * 2.2, 0, 1) };
        }
        if (t < box.lift) {
            var s = t - box.drop - DROP;
            return { lift: 0.045 * Math.exp(-s * 6) * Math.abs(Math.sin(s * 16)), alpha: 1 };
        }
        var q = (t - box.lift) / LIFT;
        return { lift: q * q * q * FALL * 1.1, alpha: 1 - smooth(0.1, 1, q) };
    }

    /* A cube of the sandbox: its visible faces shaded by the light, a faint
       frame inset on each, the bevel of a solid block, its edges, and the
       plane of light across it when it passes. */
    function drawBlock(block, state, scanY) {
        var y0 = block.layer * SIDE + state.lift;
        var y1 = y0 + SIDE;
        var c = corners(block.x - HALF, y0, block.z - HALF, block.x + HALF, y1, block.z + HALF);
        var pts = c.map(function (p) {
            return project(p);
        });
        ctx.globalAlpha = state.alpha;
        ctx.lineWidth = 1;
        FACES.forEach(function (face) {
            var poly = face.idx.map(function (i) {
                return pts[i];
            });
            if (area(poly) >= 0) {
                return;
            }
            var n = face.normal;
            var light = 0.32 + 0.68 * Math.max(0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]);
            var g = Math.round(14 + 66 * light);
            path(poly);
            ctx.fillStyle = "rgb(" + g + "," + (g + 2) + "," + (g + 7) + ")";
            ctx.fill();

            var center = [
                block.x + n[0] * HALF,
                (y0 + y1) / 2 + n[1] * HALF,
                block.z + n[2] * HALF,
            ];
            path(
                face.idx.map(function (i) {
                    return project(lerp(center, c[i], 0.78));
                })
            );
            ctx.strokeStyle = "rgba(255,255,255," + (0.05 + 0.07 * light).toFixed(3) + ")";
            ctx.stroke();

            if (n[1] === 0 && scanY !== null && scanY > y0 && scanY < y1) {
                /* The face as bottom and top edges, for the line of the scan. */
                var bottom = face.idx
                    .map(function (i) {
                        return c[i];
                    })
                    .filter(function (p) {
                        return p[1] === y0;
                    });
                var top = bottom.map(function (p) {
                    return [p[0], y1, p[2]];
                });
                var h = (scanY - y0) / SIDE;
                var l = project(lerp(bottom[0], top[0], h));
                var r = project(lerp(bottom[1], top[1], h));
                ctx.globalCompositeOperation = "lighter";
                glowLine(l, r, 1, 0.75 * state.alpha, [210, 216, 255]);
                ctx.globalCompositeOperation = "source-over";
            }
            path(poly);
            ctx.strokeStyle = "rgba(255,255,255,0.24)";
            ctx.stroke();
        });
        ctx.globalAlpha = 1;
    }

    /* The plane of light, as the ring it draws on the walls of the cube and
       a faint sheet; `front` picks the half of the ring in front of the
       cubes or the half behind them. */
    function drawScan(scanY, seen, front, strength) {
        var ring = [
            [-CUBE, scanY, -CUBE],
            [CUBE, scanY, -CUBE],
            [CUBE, scanY, CUBE],
            [-CUBE, scanY, CUBE],
        ].map(function (p) {
            return project(p);
        });
        /* The wall each side of the ring lies on: -z, +x, +z, -x. */
        var walls = [0, 3, 1, 2];
        ctx.globalCompositeOperation = "lighter";
        if (!front) {
            path(ring);
            ctx.fillStyle = rgba(INDIGO, 0.07 * strength);
            ctx.fill();
        }
        for (var i = 0; i < 4; i++) {
            if (!!seen[walls[i]] === front) {
                glowLine(ring[i], ring[(i + 1) % 4], 1.2, (front ? 0.85 : 0.45) * strength, [214, 220, 255]);
            }
        }
        ctx.globalCompositeOperation = "source-over";
    }

    /* The glass: faint faces, the back edges dim, the front ones bright,
       the construction lines that rise from the top corners, and a dot on
       each corner. `back` picks the half to draw. */
    function drawGlass(pts, seen, back, bright, wipeY) {
        ctx.globalCompositeOperation = "lighter";
        FACES.forEach(function (face, f) {
            if (!!seen[f] === back) {
                return;
            }
            var poly = face.idx.map(function (i) {
                return pts[i];
            });
            path(poly);
            var top = Math.min(poly[0][1], poly[1][1], poly[2][1], poly[3][1]);
            var bottom = Math.max(poly[0][1], poly[1][1], poly[2][1], poly[3][1]);
            var gradient = ctx.createLinearGradient(0, top, 0, bottom);
            var a = back ? 0.025 : 0.05;
            gradient.addColorStop(0, rgba(WHITE, a * 1.6));
            gradient.addColorStop(1, rgba(WHITE, a * 0.35));
            ctx.fillStyle = gradient;
            ctx.fill();
        });
        EDGES.forEach(function (edge, e) {
            var front = EDGE_FACES[e].some(function (f) {
                return seen[f];
            });
            if (front === back) {
                return;
            }
            var a = pts[edge[0]];
            var b = pts[edge[1]];
            var alpha = (back ? 0.3 : 0.9) * bright;
            if (wipeY !== null) {
                /* The wipe of a fresh sandbox: a light that climbs the edges. */
                var ya = CUBE_CORNERS[edge[0]][1];
                var yb = CUBE_CORNERS[edge[1]][1];
                var mid = (ya + yb) / 2;
                alpha += 0.6 * Math.exp(-Math.pow((mid - wipeY) / 0.35, 2));
            }
            glowLine(a, b, back ? 1 : 1.3, Math.min(1, alpha));
        });
        if (!back) {
            /* Construction lines above the top corners, dotted and fading. */
            ctx.setLineDash([2, 5]);
            [2, 3, 6, 7].forEach(function (i) {
                var base = pts[i];
                var tip = project([CUBE_CORNERS[i][0], HEIGHT + 1.5, CUBE_CORNERS[i][2]]);
                var gradient = ctx.createLinearGradient(base[0], base[1], tip[0], tip[1]);
                gradient.addColorStop(0, rgba(WHITE, 0.45));
                gradient.addColorStop(1, rgba(WHITE, 0));
                ctx.strokeStyle = gradient;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(base[0], base[1]);
                ctx.lineTo(tip[0], tip[1]);
                ctx.stroke();
                var dot = project([CUBE_CORNERS[i][0], HEIGHT + 0.75, CUBE_CORNERS[i][2]]);
                glow(GLOW_WHITE, dot[0], dot[1], 5, 0.5);
            });
            ctx.setLineDash([]);
            /* A dot on each corner of a face that is seen; the corner hidden
               behind the contents stays dark. */
            pts.forEach(function (p, i) {
                var shown = FACES.some(function (face, f) {
                    return seen[f] && face.idx.indexOf(i) >= 0;
                });
                if (shown) {
                    glow(GLOW_WHITE, p[0], p[1], 9 * p[2], 0.55 + 0.4 * flash);
                }
            });
        }
        ctx.globalCompositeOperation = "source-over";
    }

    /* Advances the pulses and the flashes by `dt` seconds. */
    function step(now, dt, t) {
        flash *= Math.exp(-dt * 2.4);
        landing *= Math.exp(-dt * 3);
        BLOCKS.forEach(function (box) {
            var landed = box.drop + DROP;
            if (t >= landed && t - dt < landed) {
                landing = 1;
            }
        });
        if (reduced) {
            return;
        }
        var busy = smooth(3.0, 3.6, t) * (1 - smooth(8.6, 9.2, t));
        if (now >= nextPulse && pulses.length < PULSE_CAP) {
            spawnPulse(now);
            var range = busy > 0.5 ? PULSE_BUSY : PULSE_IDLE;
            nextPulse = now + range[0] + Math.random() * (range[1] - range[0]);
        }
        pulses = pulses.filter(function (pulse) {
            if (now - pulse.start < pulse.duration) {
                return true;
            }
            flash = Math.min(1, flash + 0.3);
            pings.push({ p: pulsePoint(pulse, SLAB), start: now });
            return false;
        });
        pings = pings.filter(function (ping) {
            return now - ping.start < 0.9;
        });
    }

    /* The height of the plane of light at `t` of the cycle, or `null`. */
    function scanAt(t) {
        if (reduced) {
            return null;
        }
        for (var i = 0; i < SWEEPS.length; i++) {
            var sweep = SWEEPS[i];
            if (t >= sweep[0] && t <= sweep[1]) {
                var p = (t - sweep[0]) / (sweep[1] - sweep[0]);
                return 0.04 + p * (HEIGHT - 0.08);
            }
        }
        return null;
    }

    /* Draws a frame. */
    function draw(now, t) {
        frame(now);
        ctx.clearRect(0, 0, size.width, size.height);
        var busy = reduced ? 0.4 : smooth(3.0, 3.6, t) * (1 - smooth(8.6, 9.2, t));
        var bright = 0.62 + 0.22 * busy + 0.35 * flash;
        var scanY = scanAt(t);
        var scanStrength = 1;
        if (scanY !== null) {
            var sweep = SWEEPS[t < SWEEPS[1][0] ? 0 : 1];
            scanStrength = smooth(sweep[0], sweep[0] + 0.3, t) * (1 - smooth(sweep[1] - 0.3, sweep[1], t));
        }
        var wipeY = !reduced && t >= WIPE[0] && t <= WIPE[1]
            ? -0.4 + ((t - WIPE[0]) / (WIPE[1] - WIPE[0])) * (HEIGHT + 0.8)
            : null;

        ctx.globalCompositeOperation = "lighter";
        drawHalo();
        drawGrid();
        drawGlints(now);
        drawGhosts(now);
        drawPulses(now);
        ctx.globalCompositeOperation = "source-over";

        var pts = CUBE_CORNERS.map(function (p) {
            return project(p);
        });
        var seen = [];
        FACES.forEach(function (face, f) {
            seen[f] = area(face.idx.map(function (i) {
                return pts[i];
            })) < 0;
        });

        drawSlab(bright);
        drawGlass(pts, seen, true, bright, wipeY);
        if (scanY !== null) {
            drawScan(scanY, seen, false, scanStrength);
        }

        /* The cubes, lower layer first, then from the back. */
        var order = BLOCKS.map(function (box) {
            return { box: box, state: blockState(box, t), depth: project([box.x, 0, box.z])[3] };
        })
            .filter(function (item) {
                return item.state;
            })
            .sort(function (a, b) {
                return a.box.layer - b.box.layer || a.depth - b.depth;
            });
        order.forEach(function (item) {
            drawBlock(item.box, item.state, scanY);
        });

        if (scanY !== null) {
            drawScan(scanY, seen, true, scanStrength);
        }
        drawGlass(pts, seen, false, bright, wipeY);
    }

    /* Fits the canvas to the hero at the device pixel ratio, capped at 2.
       Setting the bitmap size clears the canvas, so a still frame is drawn
       again. */
    function resize() {
        var rect = hero.getBoundingClientRect();
        var width = Math.max(1, Math.round(rect.width));
        var height = Math.max(1, Math.round(rect.height));
        var dpr = Math.min(2, window.devicePixelRatio || 1);
        var content = hero.querySelector(".fs-hero__content");
        var room = content ? content.getBoundingClientRect().top - rect.top : height * 0.4;
        size.room = Math.max(120, room);
        if (width === size.width && height === size.height && dpr === size.dpr) {
            return;
        }
        size.width = width;
        size.height = height;
        size.dpr = dpr;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        if (reduced) {
            draw(0, 5);
        }
    }

    /* Makes the install command of the hero copy itself on a click. */
    function bindCopy() {
        var button = document.querySelector(".fs-hero__install");
        if (!button || button.dataset.bound) {
            return;
        }
        button.dataset.bound = "true";
        var label = button.querySelector(".fs-hero__copied");
        button.addEventListener("click", function () {
            if (!navigator.clipboard) {
                return;
            }
            navigator.clipboard.writeText(button.dataset.copy).then(function () {
                label.textContent = "Copied";
                window.setTimeout(function () {
                    label.textContent = "";
                }, 1500);
            });
        });
    }

    /* Takes the hero of the current page, if any, and runs the loop on its
       canvas. A page without a hero, or whose hero is already in hand,
       changes nothing. The hero is watched by a `ResizeObserver` rather than
       measured once: right after an instant navigation it has not reached
       its final height yet. The loop keeps its generation and stops as soon
       as a later mount has moved on; the time step is clamped so that a tab
       coming back from the background does not jump, and nothing is drawn
       while the hero is scrolled out of sight. */
    function mount() {
        bindCopy();
        var next = document.querySelector(".fs-hero__canvas");
        if (next === canvas) {
            return;
        }
        generation += 1;
        if (observer) {
            observer.disconnect();
            observer = null;
        }
        if (visibility) {
            visibility.disconnect();
            visibility = null;
        }
        window.removeEventListener("resize", resize);
        canvas = next;
        hero = next ? next.parentNode : null;
        ctx = next && next.getContext ? next.getContext("2d") : null;
        if (!hero || !ctx) {
            canvas = null;
            return;
        }
        size.width = 0;
        size.height = 0;
        if (!ghosts.length) {
            for (var g = 0; g < GHOSTS; g++) {
                var ghost = { x: -4, z: -2, half: 0.2, start: 0, hold: 3, until: 0 };
                ghosts.push(ghost);
                spawnGhost(ghost, 0);
                if (reduced) {
                    ghost.start = -10;
                    ghost.until = 1e9;
                }
            }
        }
        resize();
        if (typeof ResizeObserver === "function") {
            observer = new ResizeObserver(resize);
            observer.observe(hero);
        } else {
            window.addEventListener("resize", resize);
        }
        if (typeof IntersectionObserver === "function") {
            visibility = new IntersectionObserver(function (entries) {
                visible = entries[entries.length - 1].isIntersecting;
            });
            visibility.observe(hero);
        }
        if (reduced) {
            draw(0, 5);
            return;
        }
        last = 0;
        var token = generation;
        window.requestAnimationFrame(function loop(timestamp) {
            if (token !== generation) {
                return;
            }
            var dt = last ? Math.min(0.05, (timestamp - last) / 1000) : 0;
            last = timestamp;
            if (visible) {
                elapsed += dt;
                var t = elapsed % CYCLE;
                step(elapsed, dt, t);
                draw(elapsed, t);
            }
            window.requestAnimationFrame(loop);
        });
    }

    /* `document$` is the theme's observable of the current document: it
       emits once now and again after every instant navigation. */
    if (window.document$ && typeof window.document$.subscribe === "function") {
        window.document$.subscribe(mount);
    } else {
        mount();
    }
})();
