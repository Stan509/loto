fn main() {
    tonic_build::configure()
        .out_dir("src/proto")
        .compile(&["proto/validator.proto"], &["proto"])
        .expect("Failed to compile proto");
}
